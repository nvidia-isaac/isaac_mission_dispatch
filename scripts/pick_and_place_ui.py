"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import requests
import time
import argparse
from urllib.error import HTTPError
import numpy as np
import cv2
from websockets.sync.client import connect
import base64
import sys
from threading import Thread


class BoundingBoxViewer:
    """Pick and Place UI"""
    def __init__(self, master, params):
        self.master = master
        self.args = params
        self.master.title("Bounding Box Viewer")

        # Robot name input
        tk.Label(self.master, text="Robot Name:").pack()
        self.robot_name_entry = tk.Entry(self.master)
        self.robot_name_entry.pack()

        # Button to run object detection
        run_button = tk.Button(self.master, text="Run Object Detection",
                               command=self.run_object_detection)
        run_button.pack()

        # Main canvas for image display (initially hidden)
        self.canvas = tk.Canvas(self.master, cursor="crosshair")
        self.canvas.pack(expand=tk.YES, fill=tk.BOTH)
        self.canvas.pack_forget()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Input fields for place_pose (initially hidden)
        self.input_frame = tk.Frame(self.master)
        tk.Label(self.input_frame, text="place_position_x:").pack()
        self.place_t_x_entry = tk.Entry(self.input_frame)
        self.place_t_x_entry.pack()

        tk.Label(self.input_frame, text="place_position_y:").pack()
        self.place_t_y_entry = tk.Entry(self.input_frame)
        self.place_t_y_entry.pack()

        tk.Label(self.input_frame, text="place_position_z:").pack()
        self.place_t_z_entry = tk.Entry(self.input_frame)
        self.place_t_z_entry.pack()

        tk.Label(self.input_frame, text="place_rotation_x:").pack()
        self.place_r_x_entry = tk.Entry(self.input_frame)
        self.place_r_x_entry.pack()

        tk.Label(self.input_frame, text="place_rotation_y:").pack()
        self.place_r_y_entry = tk.Entry(self.input_frame)
        self.place_r_y_entry.pack()

        tk.Label(self.input_frame, text="place_rotation_z:").pack()
        self.place_r_z_entry = tk.Entry(self.input_frame)
        self.place_r_z_entry.pack()

        tk.Label(self.input_frame, text="place_rotation_w:").pack()
        self.place_r_w_entry = tk.Entry(self.input_frame)
        self.place_r_w_entry.pack()

        # Submit button
        submit_button = tk.Button(self.input_frame, text="Submit",
                                  command=self.submit_pickplace_request)
        submit_button.pack()

        # object ids input
        tk.Label(self.input_frame, text="Object IDs:").pack()
        self.object_ids_entry = tk.Entry(self.input_frame)
        self.object_ids_entry.pack()

        # Button to clear objects
        clear_button = tk.Button(self.input_frame, text="Clear Objects",
                                 command=self.clear_objects)
        clear_button.pack()

        # Image and bounding box data
        self.image = None
        self.tk_image = None
        self.bboxes = []
        self.selected_bbox = None  # To track the selected bounding box

        self.mission_dispatch_uri = args.mission_dispatch_uri
        self.robot_ws_uri = args.robot_ws_uri
        self.image_topic = args.image_topic

    def encoding_to_dtype_with_channels(self, encoding):
        if encoding not in ["bgr8", "rgb8"]:
            raise ValueError
        return "uint8", 3

    def imgmsg_to_cv2(self, img_msg):
        dtype, n_channels = self.encoding_to_dtype_with_channels(img_msg["encoding"])
        dtype = np.dtype(dtype)
        dtype = dtype.newbyteorder(">" if img_msg["is_bigendian"] else "<")
        img_buf = base64.b64decode(img_msg["data"])

        if n_channels == 1:
            img = np.ndarray(shape=(img_msg["height"], int(img_msg["step"]/dtype.itemsize)),
                            dtype=dtype, buffer=img_buf) # type: ignore
            img = np.ascontiguousarray(img[:img_msg["height"], :img_msg["width"]])
        else:
            img_width = int(img_msg["step"]/dtype.itemsize/n_channels)
            img = np.ndarray(shape=(img_msg["height"], img_width, n_channels),
                            dtype=dtype, buffer=img_buf)
            img = np.ascontiguousarray(img[:img_msg["height"], :img_msg["width"], :])
        # If the byte order is different between the message and the system.
        if img_msg["is_bigendian"] == (sys.byteorder == "little"):
            print("swap")
            img = img.byteswap().newbyteorder()
        if (img_msg["encoding"] == "bgr8"):
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img)
        return pil_img

    @property
    def robot_name(self):
        return self.robot_name_entry.get().strip()

    def run_object_detection(self):
        if not self.robot_name:
            print("Robot name is required.")
            return

        # Simulate API call to run object detection (Replace with actual API call)
        print(f"Running object detection for robot: {self.robot_name}")
        result = self.submit_object_detection_request()
        success = False
        # Wait for detection results
        while True:
            mission = self.make_request_with_logs(
                "get",
                f"{self.mission_dispatch_uri}/mission/{result['name']}",
                "Failed to get mission status",
                "Get mission status")
            if mission["status"]["state"] == "COMPLETED":
                detections = self.make_request_with_logs(
                    "get",
                    f"{self.mission_dispatch_uri}/detection_results/{self.robot_name}",
                    "Failed to get detections",
                    "Get detection results")
                self.bboxes = detections["status"]["detected_objects"]
                success = True
                break
            elif mission["status"]["state"] == "FAILED":
                print("Failed to get objects. Please retry.")
                break
            time.sleep(0.5)
        if not success:
            return
        # Load image and bounding boxes
        while self.image is None:
            time.sleep(0.1)
        self.display_image_with_bboxes()
        # Show the canvas and input fields
        self.canvas.pack(expand=tk.YES, fill=tk.BOTH)
        self.input_frame.pack()


    def clear_objects(self):
        if not self.robot_name:
            print("Robot name is required.")
            return

        action = {
            "action_type": "clear_objects",
            "action_parameters": {
                "object_ids": self.place_t_x_entry.get()
            }
        }
        data = {
            "robot": self.robot_name,
            "mission_tree": [
                {
                    "action": action
                }
            ]
        }

        # POST request to API endpoint
        self.make_request_with_logs("post", f"{self.mission_dispatch_uri}/mission/",
                                    "Post mission error",
                                    "Mission control accepted clear objects mission",
                                    json=data)


    def display_image_with_bboxes(self):
        # Draw bounding boxes and labels on the image
        self.annotated_image = self.image.copy() # type: ignore
        draw = ImageDraw.Draw(self.annotated_image)
        font = ImageFont.load_default()  # Revert to default font

        for bbox in self.bboxes:
            center = bbox["bbox2d"]["center"]
            size_x = bbox["bbox2d"]["size_x"]
            size_y = bbox["bbox2d"]["size_y"]
            x1 = center["x"] - size_x / 2
            y1 = center["y"] - size_y / 2
            x2 = center["x"] + size_x / 2
            y2 = center["y"] + size_y / 2
            object_id = bbox["object_id"]
            class_id = bbox["class_id"]

            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            draw.text((x1, y1 - 10), f"{object_id}: {class_id}", fill="red", font=font)

        # Display the image on canvas
        self.tk_image = ImageTk.PhotoImage(self.annotated_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def on_canvas_hover(self, event):
        x, y = event.x, event.y
        self.canvas.delete("hover_highlight")
        for bbox in self.bboxes:
            center = bbox["bbox2d"]["center"]
            size_x = bbox["bbox2d"]["size_x"]
            size_y = bbox["bbox2d"]["size_y"]
            x1 = center["x"] - size_x / 2
            y1 = center["y"] - size_y / 2
            x2 = center["x"] + size_x / 2
            y2 = center["y"] + size_y / 2

            if x1 <= x <= x2 and y1 <= y <= y2:
                if bbox != self.selected_bbox:
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, outline="blue", width=3, tags="hover_highlight")
                break

    def on_canvas_leave(self, event):
        self.canvas.delete("hover_highlight")

    def on_canvas_click(self, event):
        x, y = event.x, event.y
        clicked = False

        # Iterate through bounding boxes and check if the click is inside any of them
        for bbox in self.bboxes:
            center = bbox["bbox2d"]["center"]
            size_x = bbox["bbox2d"]["size_x"]
            size_y = bbox["bbox2d"]["size_y"]
            x1 = center["x"] - size_x / 2
            y1 = center["y"] - size_y / 2
            x2 = center["x"] + size_x / 2
            y2 = center["y"] + size_y / 2

            # Check if click is within bounding box
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.selected_bbox = bbox
                print(f"Selected object {bbox['object_id']}")
                clicked = True
                break

        if clicked:
            # Redraw the selection highlight
            self.redraw_selection()
        else:
            # If clicked outside of any bounding boxes, clear the selection
            self.selected_bbox = None
            self.redraw_selection()

    def redraw_selection(self):
        # Redraw the image and bounding boxes
        self.display_image_with_bboxes()

        # If there is a selected bounding box, highlight it
        if self.selected_bbox:
            center = self.selected_bbox["bbox2d"]["center"]
            size_x = self.selected_bbox["bbox2d"]["size_x"]
            size_y = self.selected_bbox["bbox2d"]["size_y"]
            x1 = center["x"] - size_x / 2
            y1 = center["y"] - size_y / 2
            x2 = center["x"] + size_x / 2
            y2 = center["y"] + size_y / 2

            # Draw selection highlight
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="blue", width=3, tags="selection")

    def make_request_with_logs(self, method_name, endpoint, error_msg, success_msg, **kwargs):
        try:
            method = getattr(requests, method_name)
            response = method(endpoint, **kwargs)
            response.raise_for_status()
        except (HTTPError) as exc:
            print("endpoint HTTPError failure " + str(endpoint))
            if response:
                print(str(error_msg) + " " + str(response.text))
            else:
                print(str(error_msg) + " " + str(exc))
            raise

        print(success_msg)
        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            print("Invalid response JSON received")
            return None

    def submit_pickplace_request(self):
        if not self.selected_bbox:
            print("No object selected.")
            return
        place_pose = []
        place_pose.append(self.place_t_x_entry.get())
        place_pose.append(self.place_t_y_entry.get())
        place_pose.append(self.place_t_z_entry.get())
        place_pose.append(self.place_r_x_entry.get())
        place_pose.append(self.place_r_y_entry.get())
        place_pose.append(self.place_r_z_entry.get())
        place_pose.append(self.place_r_w_entry.get())
        if any(s == "" for s in place_pose):
            print("Place position is required.")
            return

        place_poes_str = ",".join(place_pose)

        action = {
            "action_type": "pick_and_place",
            "action_parameters": {
                "object_id": self.selected_bbox["object_id"],
                "class_id": self.selected_bbox["class_id"],
                "place_pose": place_poes_str
            }
        }
        data = {
            "robot": self.robot_name,
            "mission_tree": [
                {
                    "action": action
                }
            ]
        }

        # POST request to API endpoint
        self.make_request_with_logs("post", f"{self.mission_dispatch_uri}/mission/",
                                    "Post mission error",
                                    "Mission control accepted pickplace mission",
                                    json=data)


    def submit_object_detection_request(self):
        action = {
            "action_type": "get_objects",
            "action_parameters": {}
        }
        data = {
            "robot": self.robot_name,
            "mission_tree": [
                {
                    "action": action
                }
            ]
        }

        # POST request to API endpoint
        return self.make_request_with_logs("post", f"{self.mission_dispatch_uri}/mission/",
                                           "Post mission error",
                                           "Mission dispatch accepted obj detection mission",
                                           json=data)

    def update_image(self):
        with connect(self.robot_ws_uri) as websocket:
            subscription_message = {
                "op": "subscribe",
                "topic": self.image_topic,
                "type": "sensor_msgs/Image"
            }
            websocket.send(json.dumps(subscription_message))

            while True:
                message = websocket.recv()
                data = json.loads(message)
                img_msg = data["msg"]

                self.image = self.imgmsg_to_cv2(img_msg)

    def start_image_thread(self):
        thread = Thread(target = self.update_image)
        thread.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("mission_dispatch_uri", type=str, help="Mission Dispatch uri")
    parser.add_argument("robot_ws_uri", type=str, help="Robot websockets uri")
    parser.add_argument("image_topic", type=str, help="The ROS2 topic that published image")

    args = parser.parse_args()
    root = tk.Tk()
    app = BoundingBoxViewer(root, args)
    app.start_image_thread()
    root.mainloop()
