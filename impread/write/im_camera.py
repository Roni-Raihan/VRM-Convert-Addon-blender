# Copyright (c) 2024 Roni Raihan
# Basic script / soure code by The glTF-Blender-IO authors, see < https://github.com/KhronosGroup/glTF-Blender-IO >

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see < https://www.gnu.org/licenses/ >.

#--------------------------------------------------------------------------------
# Copyright 2018-2021 The glTF-Blender-IO authors.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import bpy
from .dasar.g2b_extras import set_extras
from .dasar.g2_binary import import_user_extensions


class BlenderCamera():
    """Blender Camera."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def create(gltf, vnode, camera_id):
        """Camera creation."""
        pycamera = gltf.data.cameras[camera_id]

        import_user_extensions('gather_import_camera_before_hook', gltf, vnode, pycamera)

        if not pycamera.name:
            pycamera.name = "Camera"

        cam = bpy.data.cameras.new(pycamera.name)
        set_extras(cam, pycamera.extras)

        # Blender create a perspective camera by default
        if pycamera.type == "orthographic":
            cam.type = "ORTHO"

            cam.ortho_scale = max(pycamera.orthographic.xmag, pycamera.orthographic.ymag) * 2

            cam.clip_start = pycamera.orthographic.znear
            cam.clip_end = pycamera.orthographic.zfar

        else:
            cam.angle_y = pycamera.perspective.yfov
            cam.lens_unit = "FOV"
            cam.sensor_fit = "VERTICAL"

            # TODO: fov/aspect ratio

            cam.clip_start = pycamera.perspective.znear
            if pycamera.perspective.zfar is not None:
                cam.clip_end = pycamera.perspective.zfar
            else:
                # Infinite projection
                cam.clip_end = 1e12  # some big number

        return cam
