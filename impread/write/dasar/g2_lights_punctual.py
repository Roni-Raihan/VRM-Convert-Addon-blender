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

class LightSpot:
    """light/spot"""
    def __init__(self, inner_cone_angle, outer_cone_angle):
        self.inner_cone_angle = inner_cone_angle
        self.outer_cone_angle = outer_cone_angle

    @staticmethod
    def from_dict(obj):
        assert isinstance(obj, dict)
        inner_cone_angle = from_union([from_float, from_none], obj.get("innerConeAngle"))
        outer_cone_angle = from_union([from_float, from_none], obj.get("outerConeAngle"))
        return LightSpot(inner_cone_angle, outer_cone_angle)

    def to_dict(self):
        result = {}
        result["innerConeAngle"] = from_union([from_float, from_none], self.inner_cone_angle)
        result["outerConeAngle"] = from_union([from_float, from_none], self.outer_cone_angle)
        return result


class Light:
    """defines a set of lights for use with glTF 2.0. Lights define light sources within a scene"""
    def __init__(self, color, intensity, spot, type, range, name, extensions, extras):
        self.color = color
        self.intensity = intensity
        self.spot = spot
        self.type = type
        self.range = range
        self.name = name
        self.extensions = extensions
        self.extras = extras

    @staticmethod
    def from_dict(obj):
        assert isinstance(obj, dict)
        color = from_union([lambda x: from_list(from_float, x), from_none], obj.get("color"))
        intensity = from_union([from_float, from_none], obj.get("intensity"))
        spot = LightSpot.from_dict(obj.get("spot"))
        type = from_str(obj.get("type"))
        range = from_union([from_float, from_none], obj.get("range"))
        name = from_union([from_str, from_none], obj.get("name"))
        extensions = from_union([lambda x: from_dict(lambda x: from_dict(lambda x: x, x), x), from_none],
                                obj.get("extensions"))
        extras = obj.get("extras")
        return Light(color, intensity, spot, type, range, name, extensions, extras)

    def to_dict(self):
        result = {}
        result["color"] = from_union([lambda x: from_list(to_float, x), from_none], self.color)
        result["intensity"] = from_union([from_float, from_none], self.intensity)
        result["spot"] = from_union([lambda x: to_class(LightSpot, x), from_none], self.spot)
        result["type"] = from_str(self.type)
        result["range"] = from_union([from_float, from_none], self.range)
        result["name"] = from_union([from_str, from_none], self.name)
        result["extensions"] = from_union([lambda x: from_dict(lambda x: from_dict(lambda x: x, x), x), from_none],
                                          self.extensions)
        result["extras"] = self.extras
        return result
