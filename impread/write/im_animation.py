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
from mathutils import Vector
from .dasar.g2_binary import import_user_extensions, BinaryData
from .im_vnode import VNode

#--------------------------------------------------------
class BlenderWeightAnim():
    """Blender ShapeKey Animation."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def anim(gltf, anim_idx, vnode_id):
        """Manage animation."""
        vnode = gltf.vnodes[vnode_id]

        node_idx = vnode.mesh_node_idx

        import_user_extensions('gather_import_animation_weight_before_hook', gltf, vnode, gltf.data.animations[anim_idx])

        if node_idx is None:
            return

        node = gltf.data.nodes[node_idx]
        obj = vnode.blender_object
        fps = bpy.context.scene.render.fps

        animation = gltf.data.animations[anim_idx]

        if anim_idx not in node.animations.keys():
            return

        for channel_idx in node.animations[anim_idx]:
            channel = animation.channels[channel_idx]
            if channel.target.path == "weights":
                break
        else:
            return

        name = animation.track_name + "_" + obj.name
        action = bpy.data.actions.new(name)
        action.id_root = "KEY"
        gltf.needs_stash.append((obj.data.shape_keys, action))

        keys = BinaryData.get_data_from_accessor(gltf, animation.samplers[channel.sampler].input)
        values = BinaryData.get_data_from_accessor(gltf, animation.samplers[channel.sampler].output)

        # retrieve number of targets
        pymesh = gltf.data.meshes[gltf.data.nodes[node_idx].mesh]
        nb_targets = len(pymesh.shapekey_names)

        if animation.samplers[channel.sampler].interpolation == "CUBICSPLINE":
            offset = nb_targets
            stride = 3 * nb_targets
        else:
            offset = 0
            stride = nb_targets

        coords = [0] * (2 * len(keys))
        coords[::2] = (key[0] * fps for key in keys)

        for sk in range(nb_targets):
            if pymesh.shapekey_names[sk] is not None: # Do not animate shapekeys not created
                coords[1::2] = (values[offset + stride * i + sk][0] for i in range(len(keys)))
                kb_name = pymesh.shapekey_names[sk]
                data_path = 'key_blocks["%s"].value' % bpy.utils.escape_identifier(kb_name)

                make_fcurve(
                    action,
                    coords,
                    data_path=data_path,
                    group_name="ShapeKeys",
                    interpolation=animation.samplers[channel.sampler].interpolation,
                )

                # Expand weight range if needed
                kb = obj.data.shape_keys.key_blocks[kb_name]
                min_weight = min(coords[1:2])
                max_weight = max(coords[1:2])
                if min_weight < kb.slider_min: kb.slider_min = min_weight
                if max_weight > kb.slider_max: kb.slider_max = max_weight

        import_user_extensions('gather_import_animation_weight_after_hook', gltf, vnode, animation)

#----------------------------------------------------------------
def simulate_stash(obj, track_name, action, start_frame=None):
    # Simulate stash :
    # * add a track
    # * add an action on track
    # * lock & mute the track
    if not obj.animation_data:
        obj.animation_data_create()
    tracks = obj.animation_data.nla_tracks
    new_track = tracks.new(prev=None)
    new_track.name = track_name
    if start_frame is None:
        start_frame = bpy.context.scene.frame_start
    _strip = new_track.strips.new(action.name, start_frame, action)
    new_track.lock = True
    new_track.mute = True

def restore_animation_on_object(obj, anim_name):
    if not getattr(obj, 'animation_data', None):
        return

    for track in obj.animation_data.nla_tracks:
        if track.name != anim_name:
            continue
        if not track.strips:
            continue

        obj.animation_data.action = track.strips[0].action
        return

    obj.animation_data.action = None

def make_fcurve(action, co, data_path, index=0, group_name='', interpolation=None):
    try:
        fcurve = action.fcurves.new(data_path=data_path, index=index, action_group=group_name)
    except:
        # Some non valid files can have multiple target path
        return None

    fcurve.keyframe_points.add(len(co) // 2)
    fcurve.keyframe_points.foreach_set('co', co)

    # Setting interpolation
    ipo = {
        'CUBICSPLINE': 'BEZIER',
        'LINEAR': 'LINEAR',
        'STEP': 'CONSTANT',
    }[interpolation or 'LINEAR']
    ipo = bpy.types.Keyframe.bl_rna.properties['interpolation'].enum_items[ipo].value
    fcurve.keyframe_points.foreach_set('interpolation', [ipo] * len(fcurve.keyframe_points))

    # For CUBICSPLINE, also set the handle types to AUTO
    if interpolation == 'CUBICSPLINE':
        ty = bpy.types.Keyframe.bl_rna.properties['handle_left_type'].enum_items['AUTO'].value
        fcurve.keyframe_points.foreach_set('handle_left_type', [ty] * len(fcurve.keyframe_points))
        fcurve.keyframe_points.foreach_set('handle_right_type', [ty] * len(fcurve.keyframe_points))

    fcurve.update() # force updating tangents (this may change when tangent will be managed)

    return fcurve

#---------------------------------------------------------------
class BlenderNodeAnim():
    """Blender Object Animation."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def anim(gltf, anim_idx, node_idx):
        """Manage animation targeting a node's TRS."""
        animation = gltf.data.animations[anim_idx]
        node = gltf.data.nodes[node_idx]

        if anim_idx not in node.animations.keys():
            return

        for channel_idx in node.animations[anim_idx]:
            channel = animation.channels[channel_idx]
            if channel.target.path not in ['translation', 'rotation', 'scale']:
                continue

            BlenderNodeAnim.do_channel(gltf, anim_idx, node_idx, channel)

    @staticmethod
    def do_channel(gltf, anim_idx, node_idx, channel):
        animation = gltf.data.animations[anim_idx]
        vnode = gltf.vnodes[node_idx]
        path = channel.target.path

        import_user_extensions('gather_import_animation_channel_before_hook', gltf, animation, vnode, path, channel)

        action = BlenderNodeAnim.get_or_create_action(gltf, node_idx, animation.track_name)

        keys = BinaryData.get_data_from_accessor(gltf, animation.samplers[channel.sampler].input)
        values = BinaryData.get_data_from_accessor(gltf, animation.samplers[channel.sampler].output)

        if animation.samplers[channel.sampler].interpolation == "CUBICSPLINE":
            # TODO manage tangent?
            values = values[1::3]

        # Convert the curve from glTF to Blender.

        if path == "translation":
            blender_path = "location"
            group_name = "Location"
            num_components = 3
            values = [gltf.loc_gltf_to_blender(vals) for vals in values]
            values = vnode.base_locs_to_final_locs(values)

        elif path == "rotation":
            blender_path = "rotation_quaternion"
            group_name = "Rotation"
            num_components = 4
            values = [gltf.quaternion_gltf_to_blender(vals) for vals in values]
            values = vnode.base_rots_to_final_rots(values)

        elif path == "scale":
            blender_path = "scale"
            group_name = "Scale"
            num_components = 3
            values = [gltf.scale_gltf_to_blender(vals) for vals in values]
            values = vnode.base_scales_to_final_scales(values)

        # Objects parented to a bone are translated to the bone tip by default.
        # Correct for this by translating backwards from the tip to the root.
        if vnode.type == VNode.Object and path == "translation":
            if vnode.parent is not None and gltf.vnodes[vnode.parent].type == VNode.Bone:
                bone_length = gltf.vnodes[vnode.parent].bone_length
                off = Vector((0, -bone_length, 0))
                values = [vals + off for vals in values]

        if vnode.type == VNode.Bone:
            # Need to animate the pose bone when the node is a bone.
            group_name = vnode.blender_bone_name
            blender_path = 'pose.bones["%s"].%s' % (
                bpy.utils.escape_identifier(vnode.blender_bone_name),
                blender_path
            )

            # We have the final TRS of the bone in values. We need to give
            # the TRS of the pose bone though, which is relative to the edit
            # bone.
            #
            #     Final = EditBone * PoseBone
            #   where
            #     Final =    Trans[ft] Rot[fr] Scale[fs]
            #     EditBone = Trans[et] Rot[er]
            #     PoseBone = Trans[pt] Rot[pr] Scale[ps]
            #
            # Solving for PoseBone gives
            #
            #     pt = Rot[er^{-1}] (ft - et)
            #     pr = er^{-1} fr
            #     ps = fs

            if path == 'translation':
                edit_trans, edit_rot = vnode.editbone_trans, vnode.editbone_rot
                edit_rot_inv = edit_rot.conjugated()
                values = [
                    edit_rot_inv @ (trans - edit_trans)
                    for trans in values
                ]

            elif path == 'rotation':
                edit_rot = vnode.editbone_rot
                edit_rot_inv = edit_rot.conjugated()
                values = [
                    edit_rot_inv @ rot
                    for rot in values
                ]

            elif path == 'scale':
                pass  # no change needed

        # To ensure rotations always take the shortest path, we flip
        # adjacent antipodal quaternions.
        if path == 'rotation':
            for i in range(1, len(values)):
                if values[i].dot(values[i-1]) < 0:
                    values[i] = -values[i]

        fps = bpy.context.scene.render.fps

        coords = [0] * (2 * len(keys))
        coords[::2] = (key[0] * fps for key in keys)

        for i in range(0, num_components):
            coords[1::2] = (vals[i] for vals in values)
            make_fcurve(
                action,
                coords,
                data_path=blender_path,
                index=i,
                group_name=group_name,
                interpolation=animation.samplers[channel.sampler].interpolation,
            )

        import_user_extensions('gather_import_animation_channel_after_hook', gltf, animation, vnode, path, channel, action)

    @staticmethod
    def get_or_create_action(gltf, node_idx, anim_name):
        vnode = gltf.vnodes[node_idx]

        if vnode.type == VNode.Bone:
            # For bones, the action goes on the armature.
            vnode = gltf.vnodes[vnode.bone_arma]

        obj = vnode.blender_object

        action = gltf.action_cache.get(obj.name)
        if not action:
            name = anim_name + "_" + obj.name
            action = bpy.data.actions.new(name)
            action.id_root = 'OBJECT'
            gltf.needs_stash.append((obj, action))
            gltf.action_cache[obj.name] = action

        return action

#---------------------------------------------------------

class BlenderAnimation():
    """Dispatch Animation to node or morph weights animation."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def anim(gltf, anim_idx):
        """Create actions/tracks for one animation."""
        # Caches the action for each object (keyed by object name)
        gltf.action_cache = {}
        # Things we need to stash when we're done.
        gltf.needs_stash = []

        import_user_extensions('gather_import_animation_before_hook', gltf, anim_idx)

        for vnode_id in gltf.vnodes:
            if isinstance(vnode_id, int):
                BlenderNodeAnim.anim(gltf, anim_idx, vnode_id)
            BlenderWeightAnim.anim(gltf, anim_idx, vnode_id)

        # Push all actions onto NLA tracks with this animation's name
        track_name = gltf.data.animations[anim_idx].track_name
        for (obj, action) in gltf.needs_stash:
            simulate_stash(obj, track_name, action)

        import_user_extensions('gather_import_animation_after_hook', gltf, anim_idx, track_name)

        if hasattr(bpy.data.scenes[0], 'gltf2_animation_tracks') is False:
            return

        if track_name not in [track.name for track in bpy.data.scenes[0].gltf2_animation_tracks]:
            new_ = bpy.data.scenes[0].gltf2_animation_tracks.add()
            new_.name = track_name
        # reverse order, as animation are created in reverse order (because of NLA adding tracks are reverted)
        bpy.data.scenes[0].gltf2_animation_tracks.move(len(bpy.data.scenes[0].gltf2_animation_tracks)-1, 0)

    @staticmethod
    def restore_animation(gltf, animation_name):
        """Restores the actions for an animation by its track name."""
        for vnode_id in gltf.vnodes:
            vnode = gltf.vnodes[vnode_id]
            if vnode.type == VNode.Bone:
                obj = gltf.vnodes[vnode.bone_arma].blender_object
            elif vnode.type == VNode.Object:
                obj = vnode.blender_object
            else:
                continue

            restore_animation_on_object(obj, animation_name)
            if obj.data and hasattr(obj.data, 'shape_keys'):
                restore_animation_on_object(obj.data.shape_keys, animation_name)
