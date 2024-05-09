# Copyright (c) 2024 Roni Raihan
# Copyright (c) 2020-2024 kitsune.ONE team.
# Basic script / soure code by kitsune.ONE team. see < https://github.com/kitsune-ONE-team/KITSUNETSUKI-Asset-Tools >.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy


class Mode(object):
    def __init__(self, mode):
        self._mode = mode

    def __enter__(self):
        bpy.ops.object.mode_set(mode=self._mode)

    def __exit__(self, *args, **kw):
        bpy.ops.object.mode_set(mode='OBJECT')
