"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""
import argparse
import json
from typing import Any, AsyncGenerator, Optional
import uuid

import fastapi
import psycopg
from psycopg import sql

from packages import objects
from packages.database import common


async def initialize_database(connection: psycopg.AsyncConnection):
    cursor = connection.cursor()
    for obj in objects.ALL_OBJECTS:
        await cursor.execute(f"""CREATE TABLE IF NOT EXISTS {obj.table_name()} (
            name VARCHAR(100) PRIMARY KEY NOT NULL,
            lifecycle VARCHAR(100) NOT NULL,
            spec jsonb NOT NULL,
            status jsonb NOT NULL);""")
    await connection.commit()


class PostgresWatcher(common.Watcher):
    """ Watches for updates to objects in a postgres database """
    def __init__(self, connection: psycopg.AsyncConnection, object_class: objects.ApiObjectType,
                 publisher_id: uuid.UUID):
        self._connection = connection
        self._object_class = object_class
        self._publisher_id = publisher_id

    async def watch(self) -> AsyncGenerator[objects.ApiObject, None]:
        async with self._connection:
            async with self._connection.cursor() as cursor:
                await cursor.execute(f"LISTEN {self._object_class.table_name()};")

                # Return the value of all known objects in the db
                query = f"SELECT * FROM {self._object_class.table_name()};"
                await cursor.execute(query)
                values = await cursor.fetchall()
                objs = [self._object_class(name=name,
                                           lifecycle=objects.ObjectLifecycleV1[lifecycle],
                                           status=status, **spec)
                        for name, lifecycle, spec, status in values]
                for obj in objs:
                    yield obj

                # Now handle all notifications
                async for notification in self._connection.notifies():
                    publisher, obj_json = notification.payload.split(" ", 1)

                    # Ignore notifications caused by our changes
                    if self._publisher_id == uuid.UUID(publisher):
                        continue

                    yield self._object_class(**json.loads(obj_json))

    def close(self):
        pass


class PostgresDatabase(common.Database):
    """ Stores and retrieves api objects in a postgres database """
    def __init__(self, dbname: str, user: str, password: str, host: str, port: int):
        self._auth = f"dbname={dbname} user={user} host={host} password={password} port={port}"
        self._connection: Optional[psycopg.AsyncConnection] = None

    async def async_init(self):
        await self._get_connection()

    async def _get_connection(self) -> psycopg.AsyncConnection:
        if self._connection is None:
            self._connection = await psycopg.AsyncConnection.connect(self._auth)
            await initialize_database(self._connection)
        return self._connection

    async def _get_listen_connection(self) -> psycopg.AsyncConnection:
        connection = await psycopg.AsyncConnection.connect(self._auth, autocommit=True)
        return connection

    async def _notify(self, cursor, obj: objects.ApiObject, publisher_id: uuid.UUID):
        message = f"{str(publisher_id)} {obj.json()}"
        await cursor.execute(
            f"NOTIFY {obj.table_name()}, {sql.Literal(message).as_string(cursor)};")

    async def _commit_update(self, cursor, object_class: objects.ApiObjectType, name: str,
                             publisher_id: uuid.UUID):
        values = await cursor.fetchone()
        if values is None:
            raise fastapi.HTTPException(400,
                                        f"Could not find object {name}")
        name, lifecycle, spec, status = values
        obj = object_class(name=name,
                           lifecycle=objects.ObjectLifecycleV1[lifecycle],
                           status=status, **spec)
        await self._notify(cursor, obj, publisher_id)

    async def list_objects(self, object_class: objects.ApiObjectType):
        connection = await self._get_connection()
        async with connection.cursor() as cursor:
            await cursor.execute(f"SELECT * FROM {object_class.table_name()};")
            values = await cursor.fetchall()
            return [object_class(name=name,
                                 lifecycle=objects.ObjectLifecycleV1[lifecycle],
                                 status=status, **spec)
                    for name, lifecycle, spec, status in values]

    async def get_object(self, object_class: objects.ApiObjectType, name: str):
        connection = await self._get_connection()
        async with connection.cursor() as cursor:
            query = f"SELECT * FROM {object_class.table_name()} WHERE name = %s;"
            await cursor.execute(query, [name])
            values = await cursor.fetchone()
            if values is None:
                raise fastapi.HTTPException(
                    status_code=400,
                    detail=f"Did not find \"{object_class.get_alias()}\" with name \"{name}\"")
            obj_name, lifecycle, spec, status = values
            return object_class(name=obj_name,
                                lifecycle=objects.ObjectLifecycleV1[lifecycle],
                                status=status, **spec)

    async def create_object(self, obj: objects.ApiObject, publisher_id: uuid.UUID):
        connection = await self._get_connection()
        try:
            async with connection.cursor() as cursor:
                query = f"INSERT INTO {obj.table_name()} (name, lifecycle, spec, status) " \
                        f"VALUES (%s, %s, %s, %s);"
                await cursor.execute(query, [obj.name, obj.lifecycle.name,
                                             obj.spec.json(), obj.status.json()])
                await self._notify(cursor, obj, publisher_id)
                await connection.commit()
                return obj
        except psycopg.errors.UniqueViolation:
            await connection.rollback()
            raise fastapi.HTTPException(
                400,
                f"Object {obj.get_alias()} with name {obj.name} already exists")

    async def update_spec(self, object_class: objects.ApiObjectType, name: str, spec: Any,
                          publisher_id: uuid.UUID):
        connection = await self._get_connection()
        async with connection.cursor() as cursor:
            query = f"UPDATE {object_class.table_name()} SET spec = %s WHERE name = %s RETURNING *;"
            await cursor.execute(query, [spec.json(), name])
            await self._commit_update(cursor, object_class, name, publisher_id)
            await connection.commit()

    async def update_status(self, object_class: objects.ApiObjectType, name: str, status: Any,
                            publisher_id: uuid.UUID):
        connection = await self._get_connection()
        async with connection.cursor() as cursor:
            query = f"UPDATE {object_class.table_name()} " \
                    "SET status = %s WHERE name = %s RETURNING *;"
            await cursor.execute(query, [status.json(), name])
            await self._commit_update(cursor, object_class, name, publisher_id)
            await connection.commit()

    async def set_lifecycle(self, object_class: objects.ApiObjectType, name: str,
                            lifecycle: objects.ObjectLifecycleV1, publisher_id: uuid.UUID):
        connection = await self._get_connection()
        async with connection.cursor() as cursor:
            if lifecycle == objects.ObjectLifecycleV1.PENDING_DELETE:
                query = f"UPDATE {object_class.table_name()} " \
                        "SET lifecycle = %s WHERE name = %s RETURNING *;"
                await cursor.execute(query, ['PENDING_DELETE', name])
                await self._commit_update(cursor, object_class, name, publisher_id)
            elif lifecycle == objects.ObjectLifecycleV1.DELETED:
                query = f"DELETE FROM {object_class.table_name()} WHERE name = %s RETURNING *;"
                await cursor.execute(query, [name])
                values = await cursor.fetchone()
                if values is None:
                    raise fastapi.HTTPException(400,
                                                f"Could not find object {name}")
                name, _, spec, status = values
                obj = object_class(name=name,
                                   lifecycle=objects.ObjectLifecycleV1.DELETED,
                                   status=status, **spec)
                await self._notify(cursor, obj, publisher_id)
            await connection.commit()

    async def get_watcher(self, object_class: objects.ApiObjectType,
                          publisher_id: uuid.UUID) -> PostgresWatcher:
        connection = await self._get_listen_connection()
        return PostgresWatcher(connection, object_class, publisher_id)

def main():
    parser = argparse.ArgumentParser()
    common.WebServer.add_parser_args(parser)
    parser.add_argument("--db_name", default="mission",
                        help="The name of database to connect to in postgres")
    parser.add_argument("--db_username", default="postgres", help="The postgres username to use")
    parser.add_argument("--db_host", default="localhost",
                        help="The hostname of the postgres server")
    parser.add_argument("--db_port", default=5432, type=int,
                        help="The port to connect to on the postgres server")
    db_password_group = parser.add_mutually_exclusive_group()
    db_password_group.add_argument("--db_password", default="postgres",
                                   help="The postgres password to use")
    db_password_group.add_argument("--db_password_file",
                                   help="A file to read the postgres password from")
    args = parser.parse_args()

    if args.db_password_file is not None:
        with open(args.db_password_file) as file:
            db_password = file.read()
    else:
        db_password = args.db_password

    database = PostgresDatabase(args.db_name, args.db_username, db_password, args.db_host,
                                args.db_port)
    server = common.WebServer(database, args)
    server.run()


if __name__ == "__main__":
    main()
