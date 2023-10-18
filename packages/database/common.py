"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
import abc
import argparse
import asyncio
from typing import Any, AsyncGenerator, List, Optional
import uuid

import fastapi
import pydantic
import uvicorn

from packages import objects


LIST_DESCRIPTION = "Returns a list of all {object_type} objects in the database."
GET_DESCRIPTION = "Gets the {object_type} object with the matching id."
WATCH_DESCRIPTION = "Streams newline separated {object_type} objects. This API uses chunked \
encoding and will keep streaming until the client closes the connection. Every time a \
{object_type} object is created or modified, this will stream the object. Use this API to watch \
for changes to objects."
CREATE_DESCRIPTION = "Creates a new object of type {object_type}. If a name or prefix is not " \
"provided, a random uuid will be assigned."
UPDATE_DESCRIPTION = "Updates the object of the given {object_type}. \"lifecycle\", \"name\" " \
"and \"status\" cannot be updated."
DELETE_DESCRIPTION = "Request to delete an object of type {object_type} when given the object's \
name. The server will delete the object when there are no pending processes."

# Version of api to be shown in openapi docs
API_VERSION = "1.0.0"


class Watcher(abc.ABC):
    """ An object that allows watching for updates to objects of a given type in a database """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abc.abstractmethod
    async def watch(self) -> AsyncGenerator[objects.ApiObject, None]:
        if False:  # pylint: disable=using-constant-test
            yield

    @abc.abstractmethod
    def close(self):
        pass


class Database(abc.ABC):
    """ Represents a database that can store api objects """
    async def async_init(self):
        pass

    @abc.abstractmethod
    async def list_objects(self, object_class: objects.ApiObjectType,
                           query_params: Optional[pydantic.BaseModel] = None):
        pass

    @abc.abstractmethod
    async def get_object(self, object_class: objects.ApiObjectType, name: str):
        pass

    @abc.abstractmethod
    async def create_object(self, obj: objects.ApiObject, publisher_id: uuid.UUID):
        pass

    @abc.abstractmethod
    async def update_spec(self, object_class: objects.ApiObjectType, name: str, spec: Any,
                          publisher_id: uuid.UUID):
        pass

    @abc.abstractmethod
    async def update_status(self, object_class: objects.ApiObjectType, name: str, status: Any,
                            publisher_id: uuid.UUID):
        pass

    @abc.abstractmethod
    async def set_lifecycle(self, object_class: objects.ApiObjectType, name: str,
                            lifecycle: objects.ObjectLifecycleV1, publisher_id: uuid.UUID):
        pass

    @abc.abstractmethod
    async def get_watcher(self, object_class: objects.ApiObjectType,
                          publisher_id: uuid.UUID) -> Watcher:
        pass


class WebServer:
    """ A webserver that hosts REST APIs for accessing a database of api objects """
    def __init__(self, database: Database, args: argparse.Namespace):
        self._database = database
        self._address = args.address
        self._port = args.port
        self._controller_port = args.controller_port
        self._root_path = args.root_path

    @classmethod
    def add_parser_args(cls, parser: argparse.ArgumentParser):
        parser.add_argument("--address", default="127.0.0.1",
                            help="The address to bind to and listen on")
        parser.add_argument("--port", type=int, default=5000,
                            help="The port to host the user facing API on")
        parser.add_argument("--controller_port", type=int, default=5001,
                            help="The port to host the private, controller API on")
        parser.add_argument("--root_path", type=str, default="",
                            help="If mission dispatch is hosted behind a reverse proxy " \
                                 "set this to the url it is routed to")

    def _get_create_class(self, object_class: objects.ApiObjectType):
        class Create(object_class.get_spec_class()):  # type: ignore
            """Defines parameters used to create a new object"""
            name: Optional[str] = pydantic.Field(
                None,
                description="The unique name to give the object. If no name is given and the " \
                            "\"prefix\" field is not provided, a random id will be generated and " \
                            "used as the name")
            prefix: Optional[str] = pydantic.Field(
                None,
                description="May be used instead of the \"name\" field. If this is given, the " \
                            f"object will be given a name of the form " \
                            "<prefix>-<random id> to ensure uniqueness.")

            class Config:
                extra = "forbid"

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

                if self.name is not None and self.prefix is not None:
                    raise ValueError("Cannot have both \"name\" and \"prefix\"")

                # If a prefix is provided, use that to generate the name
                if self.prefix is not None:
                    self.name = self.prefix + "-" + object_class.get_uuid()

        Create.__name__ = object_class.__name__ + "Create"
        return Create

    def _get_spec_update_class(self, object_class: objects.ApiObjectType):
        class Update(object_class.get_spec_class()):  # type: ignore
            """Defines parameters used to update an object's spec"""
            class Config:
                extra = "forbid"

            @pydantic.root_validator(pre=True)
            def check_for_status(cls, values):
                if "status" in values:
                    raise ValueError("Attempted to update \"status\" with the external API " \
                                     "hosted on --port. This can only be done from the internal " \
                                     "API hosted on --controller_port.")
                return values


            def update_object(self, obj):
                new_fields = self.dict()
                for key, value in new_fields.items():
                    setattr(obj, key, value)


        Update.__name__ = object_class.__name__ + "Update"
        return Update

    def _get_status_update_class(self, object_class: objects.ApiObjectType):
        class Update(pydantic.BaseModel):
            """Defines parameters used to update an object's status"""
            class Config:
                extra = "forbid"

            @pydantic.root_validator(pre=True, allow_reuse=True)
            def check_for_spec(cls, values):
                spec_keys = [key for key in values if key != "status"]
                if spec_keys:
                    raise ValueError(f"Attempted to update non \"status\" keys {spec_keys} with " \
                                     "the internal API hosted on --controller_port. This can " \
                                     "only be done from the external API hosted on --port.")
                return values

            status: object_class.get_status_class()  # type: ignore
            def update_object(self, obj):
                obj.status = self.status

        Update.__name__ = object_class.__name__ + "Update"
        return Update


    def _build_lister(self, object_class: objects.ApiObjectType):
        async def func(query_params:                                       # type: ignore
                       object_class.get_query_params()=fastapi.Depends()): # type: ignore
            return await self._database.list_objects(object_class, query_params)
        return func

    def _build_creator(self, object_class: objects.ApiObjectType):
        async def func(obj: self._get_create_class(object_class),  # type: ignore
                       publisher_id: Optional[uuid.UUID] = None):
            if publisher_id is None:
                publisher_id = uuid.uuid4()
            obj = object_class(**obj.dict(), status={})
            await self._database.create_object(obj, publisher_id)
            return obj
        return func

    def _build_getter(self, object_class: objects.ApiObjectType):
        async def func(name: str):
            return await self._database.get_object(object_class, name)
        return func

    def _build_watcher(self, object_class: objects.ApiObjectType):
        async def watch(publisher_id: Optional[uuid.UUID] = None):
            if publisher_id is None:
                publisher_id = uuid.uuid4()

            with await self._database.get_watcher(object_class, publisher_id) as watcher:
                async for obj in watcher.watch():
                    yield obj.json() + "\n"

        async def func(publisher_id: Optional[uuid.UUID] = None):
            return fastapi.responses.StreamingResponse(watch(publisher_id))

        return func

    def _build_spec_updator(self, object_class: objects.ApiObjectType):
        async def func(spec: self._get_spec_update_class(object_class),  # type: ignore
                       name: str,
                       publisher_id: Optional[uuid.UUID] = None):
            if publisher_id is None:
                publisher_id = uuid.uuid4()
            await self._database.update_spec(object_class, name, spec, publisher_id)
        return func

    def _build_status_updator(self, object_class: objects.ApiObjectType):
        async def func(status: self._get_status_update_class(object_class),  # type: ignore
                       name: str,
                       publisher_id: Optional[uuid.UUID] = None):
            if publisher_id is None:
                publisher_id = uuid.uuid4()
            await self._database.update_status(object_class, name, status.status, publisher_id)
        return func

    def _build_deletor(self, object_class: objects.ApiObjectType):
        async def func(name: str,
                       publisher_id: Optional[uuid.UUID] = None):
            if publisher_id is None:
                publisher_id = uuid.uuid4()
            await self._database.set_lifecycle(object_class, name,
                                               objects.ObjectLifecycleV1.PENDING_DELETE,
                                               publisher_id)
        return func

    def _build_hard_deletor(self, object_class: objects.ApiObjectType):
        async def func(name: str,
                       publisher_id: Optional[uuid.UUID] = None):
            if publisher_id is None:
                publisher_id = uuid.uuid4()
            await self._database.set_lifecycle(object_class, name,
                                               objects.ObjectLifecycleV1.DELETED,
                                               publisher_id)
        return func

    def _build_method(self, object_class: objects.ApiObjectType, method: objects.ApiObjectMethod):
        if method.params is not None:
            async def func(params: method.params,  # type: ignore
                           name: str, publisher_id: Optional[uuid.UUID] = None):
                if publisher_id is None:
                    publisher_id = uuid.uuid4()
                obj = await self._database.get_object(object_class, name)
                ret = await method.function(obj, params)
                await self._database.update_spec(object_class, name, obj.spec, publisher_id)
                return ret
            return func
        else:
            async def func(name: str, publisher_id: Optional[uuid.UUID] = None):  # type: ignore
                # Lookup the related object
                if publisher_id is None:
                    publisher_id = uuid.uuid4()
                obj = await self._database.get_object(object_class, name)
                ret = await method.function(obj)
                await self._database.update_spec(object_class, name, obj.spec, publisher_id)
                return ret
            return func

    def _health_check(self):
        async def func():
            return {"status": "Mission Dispatch: Running"}
        return func

    def _register_common_apis(self, app: fastapi.FastAPI):
        for class_name, obj in objects.OBJECT_DICT.items():
            app.add_api_route(f"/{class_name}", self._build_lister(obj),
                              description=LIST_DESCRIPTION.format(object_type=obj.__name__),
                              response_model=List[obj], tags=[class_name])  # type: ignore
            app.add_api_route(f"/{class_name}/watch", self._build_watcher(obj),
                              description=WATCH_DESCRIPTION.format(object_type=obj.__name__),
                              response_model=obj, tags=[class_name])
            app.add_api_route(f"/{class_name}/{{name}}", self._build_getter(obj),
                              description=GET_DESCRIPTION.format(object_type=obj.__name__),
                              response_model=obj, tags=[class_name])  # type: ignore
            app.add_api_route(f"/{class_name}", self._build_creator(obj),
                              description=CREATE_DESCRIPTION.format(object_type=obj.__name__),
                              response_model=obj, methods=["POST"], tags=[class_name])
        app.add_api_route(f"/health", self._health_check(), methods=["GET"])

    def _register_controller_apis(self, app: fastapi.FastAPI):
        for class_name, obj in objects.OBJECT_DICT.items():
            app.add_api_route(f"/{class_name}/{{name}}", self._build_status_updator(obj),
                              description=UPDATE_DESCRIPTION.format(object_type=obj.__name__),
                              response_model=None, methods=["PUT"], tags=[class_name])
            app.add_api_route(f"/{class_name}/{{name}}", self._build_hard_deletor(obj),
                              description=DELETE_DESCRIPTION.format(object_type=obj.__name__),
                              response_model=None, methods=["DELETE"], tags=[class_name])

    def _register_user_apis(self, app: fastapi.FastAPI):
        for class_name, obj in objects.OBJECT_DICT.items():
            if obj.supports_spec_update():
                app.add_api_route(f"/{class_name}/{{name}}", self._build_spec_updator(obj),
                                  description=UPDATE_DESCRIPTION.format(object_type=obj.__name__),
                                  response_model=None, methods=["PUT"], tags=[class_name])
            app.add_api_route(f"/{class_name}/{{name}}", self._build_deletor(obj),
                              description=DELETE_DESCRIPTION.format(object_type=obj.__name__),
                              response_model=None, methods=["DELETE"], tags=[class_name])

            for method in obj.get_methods():
                app.add_api_route(f"/{class_name}/{{name}}/{method.name}",
                                  self._build_method(obj, method), description=method.description,
                                  response_model=method.returns, methods=["POST"],
                                  tags=[class_name])

    async def _run_servers(self, public_app, private_app):
        await self._database.async_init()
        public_server = uvicorn.Server(uvicorn.Config(public_app, port=self._port,
                                                      host=self._address))
        private_server = uvicorn.Server(uvicorn.Config(private_app, port=self._controller_port,
                                                       host=self._address))
        await asyncio.wait([public_server.serve(), private_server.serve()],
                           return_when=asyncio.FIRST_COMPLETED)

    def run(self):
        public_app = fastapi.FastAPI(root_path=self._root_path, title="Mission Dispatch API",
                                     version=API_VERSION)
        self._register_common_apis(public_app)
        self._register_user_apis(public_app)

        private_app = fastapi.FastAPI(root_path=self._root_path,
                                      title="Mission Dispatch Internal API", version=API_VERSION)
        self._register_common_apis(private_app)
        self._register_controller_apis(private_app)

        # Run the server
        event_loop = asyncio.get_event_loop()
        event_loop.run_until_complete(self._run_servers(public_app, private_app))
