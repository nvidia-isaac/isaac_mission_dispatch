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
import py_trees
from typing import Any
import packages.objects.mission as mission_object

def tree2mission_state(type: py_trees.common.Status) -> mission_object.MissionStateV1:
    if type == py_trees.common.Status.SUCCESS:
        return mission_object.MissionStateV1.COMPLETED
    elif type == py_trees.common.Status.FAILURE:
        return mission_object.MissionStateV1.FAILED
    elif type == py_trees.common.Status.RUNNING:
        return mission_object.MissionStateV1.RUNNING
    else:
        return mission_object.MissionStateV1.PENDING

def mission2tree_state(type: mission_object.MissionStateV1) -> py_trees.common.Status:
    if type == mission_object.MissionStateV1.COMPLETED:
        return py_trees.common.Status.SUCCESS
    elif type == mission_object.MissionStateV1.RUNNING:
        return py_trees.common.Status.RUNNING
    elif type == mission_object.MissionStateV1.PENDING:
        return py_trees.common.Status.INVALID
    else:
        return py_trees.common.Status.FAILURE


class ConstantBehaviorNode(py_trees.behaviour.Behaviour):
    """
    Constant behavior tree node
    """

    def __init__(self, name: str, idx: int, const_status=py_trees.common.Status.SUCCESS):
        print(
            f"Create a constant node for mission node {idx} with status {const_status}", flush=True)
        self.idx = idx
        self.name = name
        self.const_status = const_status
        super().__init__(self.name)

    @property
    def type(self) -> str:
        return "leaf"

    @property
    def is_order(self):
        """Whether this node involves sending VDA5050 orders to the robot"""
        return True

    def initialise(self):
        self.status = py_trees.common.Status.RUNNING

    def update(self) -> py_trees.common.Status:
        return self.const_status


class MissionLeafNode(py_trees.behaviour.Behaviour):
    """
    Route/action behavior tree node
    """
    def __init__(self, mission: mission_object.MissionObjectV1, idx: int,
                 status=py_trees.common.Status.INVALID):
        self.mission = mission
        self.idx = idx
        self.name = str(self.mission.mission_tree[idx].name)
        self.status = status
        super(MissionLeafNode, self).__init__(self.name)

    @property
    def type(self) -> str:
        return "leaf"

    @property
    def is_order(self):
        """Whether this node involves sending VDA5050 orders to the robot"""
        return False

    def initialise(self):
        self.status = py_trees.common.Status.RUNNING

    def update(self) -> py_trees.common.Status:
        # Update result based on order information feedback from server
        # Count PENDING orders as RUNNING since the robot might not have acknowledged the order yet
        if self.mission.status.node_status[self.name].state == \
            mission_object.MissionStateV1.PENDING:
            return py_trees.common.Status.RUNNING
        else:
            return mission2tree_state(self.mission.status.node_status[self.name].state)


class SequenceBehaviorNode(py_trees.composites.Sequence):
    """
    Sequence behavior tree node
    """
    def __init__(self, name: str, idx: int, status=py_trees.common.Status.INVALID):
        self.idx = idx
        self.name = name
        self.status = status
        super().__init__(self.name, memory=True)

    @property
    def type(self) -> str:
        return "control"

    @property
    def is_order(self):
        """Whether this node involves sending VDA5050 orders to the robot"""
        return True


class SelectorBehaviorNode(py_trees.composites.Selector):
    """
    Selector behavior tree node
    """
    def __init__(self, name: str, idx: int, status=py_trees.common.Status.INVALID):
        self.idx = idx
        self.name = name
        self.status = status
        super().__init__(self.name)

    @property
    def type(self) -> str:
        return "control"

    @property
    def is_order(self):
        """Whether this node involves sending VDA5050 orders to the robot"""
        return True


class MissionBehaviorTree():
    """Mission behavior Tree
    """
    def __init__(self, mission: mission_object.MissionObjectV1):
        # The behavior tree has an implicit sequence node as its root which is named “root”
        self.root = py_trees.composites.Sequence(name="root")
        self.mission = mission
        self.failure_reason = ""

    @property
    def current_node(self) -> Any:
        # Recursive function to extract the last running node of the tree
        return self.root.tip()

    @property
    def status(self) -> py_trees.common.Status:
        return self.root.status

    def create_behavior_tree(self):
        for i, mission_node in enumerate(self.mission.mission_tree):
            # Get parent node
            status = mission2tree_state(
                self.mission.status.node_status[str(mission_node.name)].state)
            parent = None
            for node in self.root.iterate():
                if node.name == mission_node.parent:
                    parent = node
            if parent is None:
                self.root.status = py_trees.common.Status.FAILURE
                self.failure_reason = f"Given parent {mission_node.parent} does not exist"
                return False

            # Check if this is a control node: selector or sequence
            if mission_node.type == mission_object.MissionNodeType.SELECTOR:
                parent.add_child(SelectorBehaviorNode(str(mission_node.name), i, status))
            elif mission_node.type == mission_object.MissionNodeType.SEQUENCE:
                parent.add_child(SequenceBehaviorNode(str(mission_node.name), i, status))
            # Check if this is a leaf node: route or action
            elif mission_node.type in (mission_object.MissionNodeType.ROUTE,
                                       mission_object.MissionNodeType.ACTION):
                leaf_node = MissionLeafNode(self.mission, i, status)
                parent.add_child(leaf_node)
            elif mission_node.type == mission_object.MissionNodeType.CONSTANT:
                if mission_node.constant is not None:
                    if mission_node.constant.success:
                        status = py_trees.common.Status.SUCCESS
                    else:
                        status = py_trees.common.Status.FAILURE
                    parent.add_child(ConstantBehaviorNode(str(mission_node.name), i, status))
            # Not supported mission node type
            else:
                self.info("Invalid mission node type")
        return True

    def update(self):
        self.root.tick_once()
        self.post_tick()

    def post_tick(self):
        # Update all the non-pending control node
        for node in self.root.iterate():
            if node.name != "root" and node.is_order:
                self.mission.status.node_status[node.name].state = \
                    tree2mission_state(node.status)

    def info(self, message: str):
        print(f"[Isaac Mission Dispatch (Behavior Tree)] | : "
              f"[{self.mission.name}] {message}", flush=True)
