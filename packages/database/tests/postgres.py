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
import signal
import unittest

from packages.database import client as db_client
from packages.utils import test_utils
from packages.database.tests import test_base

# The TCP port for the database to listen on
DATABASE_PORT = 5021
DATABASE_CONTROLLER_PORT = 5022
# The TCP port for the postgres db to connect on
POSTGRES_DATABASE_PORT = 5432

class TestPostgresDatabase(test_base.TestDatabase):
    @classmethod
    def setUpClass(cls):
        if cls.has_process_crashed:
            raise ValueError("Can't run test due to previous failure")

        # Register signal handler
        signal.signal(signal.SIGUSR1, cls.catch_signal)

        # Create the database and wait some time for it to start up
        cls.postgres_database, postgres_address = \
            cls.run_docker(cls, image="//packages/utils/test_utils:postgres-database-img-bundle",
                                         docker_args=["-e", "POSTGRES_PASSWORD=postgres", 
                                                      "-e", "POSTGRES_DB=mission",
                                                      "--publish", F"{str(POSTGRES_DATABASE_PORT)}:{str(POSTGRES_DATABASE_PORT)}",
                                                      "-e", "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256"],
                                         args=['postgres'])
        test_utils.wait_for_port(host=postgres_address, port=POSTGRES_DATABASE_PORT, timeout=120)
        print(f"Database setup done on {postgres_address}:{POSTGRES_DATABASE_PORT}")
        # Startup server API's
        cls.database, address = cls.run_docker(cls, image="//packages/database:postgres-img-bundle",
                                                         args=["--port", str(DATABASE_PORT),
                                                               "--controller_port", str(DATABASE_CONTROLLER_PORT),
                                                               "--db_host", postgres_address,
                                                               "--address", "0.0.0.0"])
        cls.client = db_client.DatabaseClient(f"http://{address}:{DATABASE_PORT}")
        cls.controller_client = db_client.DatabaseClient(
            f"http://{address}:{DATABASE_CONTROLLER_PORT}")
        test_utils.wait_for_port(host=address, port=DATABASE_PORT, timeout=140)
        test_utils.wait_for_port(host=address, port=DATABASE_CONTROLLER_PORT, timeout=140)


    @classmethod
    def tearDownClass(cls):
        cls.close(cls, processes=[cls.database, cls.postgres_database])



if __name__ == "__main__":
    unittest.main()
