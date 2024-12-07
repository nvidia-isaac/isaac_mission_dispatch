# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2021-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
FROM nvcr.io/nvidia/base/ubuntu:22.04_20240212
ARG DEBIAN_FRONTEND=noninteractive

# Install python
RUN apt-get update && apt-get install python3 python3-pip -y
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install bazel
RUN apt-get install wget -y
RUN wget --progress=dot:mega https://github.com/bazelbuild/bazel/releases/download/6.5.0/bazel-6.5.0-linux-x86_64 -O /usr/bin/bazel
RUN chmod +x /usr/bin/bazel

# Install docker
RUN apt-get update 
RUN apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git
RUN git config --global --add safe.directory '*'
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
RUN echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update
RUN apt-get install -y docker-ce-cli

RUN apt-get update && apt-get install libgl1-mesa-glx ffmpeg libsm6 libxext6 python3-tk -y