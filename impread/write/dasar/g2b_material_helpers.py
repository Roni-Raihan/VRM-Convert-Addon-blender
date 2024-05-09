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

# Get compatibility at export with old files
def get_gltf_node_old_name():
    return "glTF Settings"

# Old group name
def get_gltf_old_group_node_name():
    return "glTF Metallic Roughness"

def get_gltf_node_name():
    return "glTF Material Output"

def create_settings_group(name):
    gltf_node_group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    gltf_node_group.interface.new_socket("Occlusion", socket_type="NodeSocketFloat")
    thicknessFactor  = gltf_node_group.interface.new_socket("Thickness", socket_type="NodeSocketFloat", )
    thicknessFactor.default_value = 0.0
    gltf_node_group.nodes.new('NodeGroupOutput')
    gltf_node_group_input = gltf_node_group.nodes.new('NodeGroupInput')
    gltf_node_group_input.location = -200, 0
    return gltf_node_group
