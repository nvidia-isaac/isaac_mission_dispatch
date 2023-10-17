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

# Install python and dependencies
FROM nvcr.io/nvidia/base/ubuntu:20.04_x64_2022-09-23

# Install python
RUN apt-get update && apt-get install python3 python3-pip -y
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install bazel
RUN apt-get install wget -y
RUN wget --progress=dot:mega https://github.com/bazelbuild/bazel/releases/download/4.0.0/bazel-4.0.0-linux-x86_64 -O /usr/bin/bazel
RUN chmod +x /usr/bin/bazel

# Install docker
RUN apt-get update 
RUN apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
RUN echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update
RUN apt-get install -y docker-ce-cli

# Create "worker" user
ARG user_id=990
ARG group_id=990
ARG user_name=worker
ARG docker_id=134
RUN getent group $user_name || groupadd -fg $group_id $user_name
RUN id -u $user_name >/dev/null 2>&1 || useradd -mu $user_id -g $user_name $user_name
RUN getent group docker || groupadd -g $docker_id docker
RUN usermod -aG docker $user_name
# Switch to new user
USER $user_name
