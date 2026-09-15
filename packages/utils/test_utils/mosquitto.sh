#!/bin/sh
# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2021-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

# Shell script to launch inside the mosquitto-broker container
# to set the port and address

CONFIG_FILE=/mosquitto.conf

if [ $# != 2 ] ; then
    echo "usage: $0 <tcp_port> <websocket_port>"
    exit 1
fi
PORT=$1
PORT_WEBSOCKET=$2

echo "allow_anonymous true" > $CONFIG_FILE
echo "listener $PORT 0.0.0.0" >> $CONFIG_FILE
echo "listener $PORT_WEBSOCKET" >> $CONFIG_FILE
echo "protocol websockets" >> $CONFIG_FILE
mosquitto -c $CONFIG_FILE
