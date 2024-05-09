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
# along with this program.  If not, see < https://www.gnu.org/licenses/ >.

#-----------------------------------------------------------------------------------

import bpy
import math

from .dasar.matrices import get_bone_matrix, quat_to_list
from .dasar.armature import get_armature, is_left_bone, is_bone_matches
from .dasar.objects import get_parent

#from . import spec
from .dasar import spec

class ArmatureMixin(object):
    def _make_vrm_bone(self, gltf_node_id, bone):
        vrm_bone = {
            'bone': None,
            'node': gltf_node_id,
            'useDefaultValues': True,
            'extras': {
                'name': bone.name,
            }
        }

        def is_hips(bone):
            return is_bone_matches(bone, ('hips',))

        def is_upper_leg(bone, strict=True):
            names = ['thigh']
            if not strict:
                names.append('leg')
            is_upper = is_bone_matches(bone, names)
            is_child = is_hips(get_parent(bone))
            return is_upper or is_child

        def is_lower_leg(bone):
            is_lower = is_bone_matches(bone, ('calf', 'shin', 'knee'))
            is_child = is_upper_leg(get_parent(bone), strict=False)
            return is_lower or is_child

        def is_hand(bone):
            return is_bone_matches(bone, ('hand', 'wrist'))

        side = 'left' if is_left_bone(bone) else 'right'

        parents = []
        for i in range(1, 3+1):
            parent = get_parent(bone, i)
            if parent:
                parents.append(parent)

        if is_hips(bone):
            vrm_bone['bone'] = 'hips'

        elif (is_bone_matches(bone, ('upperchest',)) or
                (is_bone_matches(bone, ('spine',)) and is_hips(get_parent(bone, 3)))):
            vrm_bone['bone'] = 'upperChest'

        elif (is_bone_matches(bone, ('chest',)) or
                (is_bone_matches(bone, ('spine',)) and is_hips(get_parent(bone, 2)))):
            vrm_bone['bone'] = 'chest'

        elif is_bone_matches(bone, ('spine',)):
            vrm_bone['bone'] = 'spine'

        elif is_bone_matches(bone, ('neck',)):
            vrm_bone['bone'] = 'neck'

        elif is_bone_matches(bone, ('head',)):
            vrm_bone['bone'] = 'head'

        elif is_bone_matches(bone, ('eye',)):
            vrm_bone['bone'] = '{}Eye'.format(side)

        elif is_bone_matches(bone, ('foot', 'ankle')):
            vrm_bone['bone'] = '{}Foot'.format(side)

        elif is_lower_leg(bone):
            vrm_bone['bone'] = '{}LowerLeg'.format(side)

        elif is_upper_leg(bone):
            vrm_bone['bone'] = '{}UpperLeg'.format(side)

        elif is_bone_matches(bone, ('toe',)):
            vrm_bone['bone'] = '{}Toes'.format(side)

        elif is_bone_matches(bone, ('shoulder', 'clavicle')):
            vrm_bone['bone'] = '{}Shoulder'.format(side)

        elif is_bone_matches(bone, ('lowerarm', 'lower_arm', 'forearm', 'elbow')):
            vrm_bone['bone'] = '{}LowerArm'.format(side)

        elif is_bone_matches(bone, ('upperarm', 'upper_arm', 'arm')):
            vrm_bone['bone'] = '{}UpperArm'.format(side)

        elif any(map(is_hand, parents)):  # hand in parents -> finger
            if is_hand(get_parent(bone, 3)):  # 3 level deep parent
                part_name = 'Distal'
            elif is_hand(get_parent(bone, 2)):  # 2 level deep parent
                part_name = 'Intermediate'
            else:  # 1 level deep parent - direct parent
                part_name = 'Proximal'

            if is_bone_matches(bone, ('thumb',)):
                vrm_bone['bone'] = '{}Thumb{}'.format(side, part_name)

            elif is_bone_matches(bone, ('index',)):
                vrm_bone['bone'] = '{}Index{}'.format(side, part_name)

            elif is_bone_matches(bone, ('middle',)):
                vrm_bone['bone'] = '{}Middle{}'.format(side, part_name)

            elif is_bone_matches(bone, ('ring',)):
                vrm_bone['bone'] = '{}Ring{}'.format(side, part_name)

            elif is_bone_matches(bone, ('pinky', 'little')):
                vrm_bone['bone'] = '{}Little{}'.format(side, part_name)

        elif is_hand(bone):
            vrm_bone['bone'] = '{}Hand'.format(side)

        return vrm_bone

    def _make_vrm_spring(self, gltf_node_id, bone, armature):
        vrm_spring = {
            'comment': bone.name,
            'stiffiness': 1,  # The resilience of the swaying object (the power of returning to the initial pose)
            'gravityPower': 0,
            'dragForce': 0,  # The resistance (deceleration) of automatic animation
            'gravityDir': {
                'x': 0,
                'y': -1,
                'z': 0,
            },  # down
            'center': -1,
            'hitRadius': 0,
            'bones': [gltf_node_id],
            'colliderGroups': [],
        }

        if bone.get('vrmprop_stiffness', None) is not None:
            vrm_spring['stiffiness'] = bone.get('vrmprop_stiffness')

        if bone.get('vrmprop_gravity', None) is not None:
            vrm_spring['gravityPower'] = bone.get('vrmprop_gravity')

        if bone.get('vrmprop_amplitude', None) is not None:
            max_amp = 200
            vrmprop_amplitude = min(max_amp, bone.get('vrmprop_amplitude'))
            vrm_spring['dragForce'] = (max_amp - vrmprop_amplitude) / max_amp
        
        if bone.vrmprop_use_colliders == True:
            if bone.get('vrmprop_radius', None) is not None:
                vrm_spring['hitRadius'] = bone.get('vrmprop_radius')
            
            for i, item in enumerate(armature.data.vrmprop_grub_collider):
                item1 = item
                for item in bone.vrmprop_colliders:
                    item2 = item
                    if item1.id == item2.id and item2.aktif == True:
                        #collider_aktif = i
                        vrm_spring['colliderGroups'].append(i)

        return vrm_spring
    
    def _make_vrm_collider(self, gltf_node_id, bone):
        jc = bone.vrmprop_collider
        vrm_collider = {
            'node': gltf_node_id,
            'colliders': []
        }
        for item in jc:
            collider_data = {
                'offset' : {"x": item.offset[0], "y": item.offset[2], "z": item.offset[1]},
                'radius' : item.radius
            }
            vrm_collider['colliders'].append(collider_data)

        return vrm_collider

    def make_armature(self, parent_node, armature):
        gltf_armature = super().make_armature(parent_node, armature)

        vrm_bones = set()
        vrm_springs = set()
        vrm_colliders = set()
        
        if not len(armature.data.vrmprop_grub_collider) == 0:
            for item in enumerate(armature.data.vrmprop_grub_collider):
                sewa = {'status' : 'disewa'}
                self._root['extensions']['VRM']['secondaryAnimation']['colliderGroups'].append(sewa)
                    
        for bone_name, bone in armature.data.bones.items():
            gltf_node_id = None
            for gltf_node_id, gltf_node in enumerate(self._root['nodes']):
                if gltf_node['name'] == bone_name:
                    break
            else:
                continue

            vrm_bone = self._make_vrm_bone(gltf_node_id, bone)

            if vrm_bone['bone'] and vrm_bone['bone'] not in vrm_bones:
                vrm_bones.add(vrm_bone['bone'])
                self._root['extensions']['VRM']['humanoid']['humanBones'].append(vrm_bone)

                fp = self._root['extensions']['VRM']['firstPerson']

                if vrm_bone['bone'] == 'head':
                    fp['firstPersonBone'] = gltf_node_id
                    fp['extras'] = {'name': bone.name}

                elif vrm_bone['bone'] == 'leftEye':
                    fp.update({
                        'lookAtHorizontalOuter': {
                            'curve': [0, 0, 0, 1, 1, 1, 1, 0],
                            'xRange': 90,
                            'yRange': 10,
                        },
                        'lookAtHorizontalInner': {
                            'curve': [0, 0, 0, 1, 1, 1, 1, 0],
                            'xRange': 90,
                            'yRange': 10,
                        },
                        'lookAtVerticalDown': {
                            'curve': [0, 0, 0, 1, 1, 1, 1, 0],
                            'xRange': 90,
                            'yRange': 10,
                        },
                        'lookAtVerticalUp': {
                            'curve': [0, 0, 0, 1, 1, 1, 1, 0],
                            'xRange': 90,
                            'yRange': 10,
                        },
                    })

                    pose_bone = armature.pose.bones[bone_name]
                    for c in pose_bone.constraints:
                        if c.type == 'LIMIT_ROTATION':
                            fp['lookAtHorizontalOuter']['xRange'] = -math.degrees(c.min_x)
                            fp['lookAtHorizontalInner']['xRange'] = math.degrees(c.max_x)
                            fp['lookAtVerticalDown']['yRange'] = -math.degrees(c.min_z)
                            fp['lookAtVerticalUp']['yRange'] = math.degrees(c.max_z)
                            break

            pose_bone = armature.pose.bones[bone_name]

            if pose_bone.vrmprop_aktif and pose_bone.vrmprop_aktif == 'Spring':
                #while (pose_bone.parent and
                        #pose_bone.parent.vrmprop_aktif == 'Spring'):#.get('vrmprop_aktif', False)):
                    #pose_bone = pose_bone.parent

                if pose_bone.name not in vrm_springs:
                    vrm_spring = self._make_vrm_spring(gltf_node_id, pose_bone, armature)
                    vrm_springs.add(pose_bone.name)
                    self._root['extensions']['VRM']['secondaryAnimation']['boneGroups'].append(vrm_spring)
            
            if pose_bone.vrmprop_aktif and pose_bone.vrmprop_aktif == 'Collider':
                if pose_bone.name not in vrm_colliders:
                    vrm_collider = self._make_vrm_collider(gltf_node_id, pose_bone)
                    vrm_colliders.add(pose_bone.name)
                    for i, item in enumerate(armature.data.vrmprop_grub_collider):
                        if item.id == pose_bone.vrmprop_collider_id:
                            index = i
                            ganti = self._root['extensions']['VRM']['secondaryAnimation']['colliderGroups'].pop(index)
                            self._root['extensions']['VRM']['secondaryAnimation']['colliderGroups'].insert(index, vrm_collider)#.append(vrm_collider)
                            break
                

        return gltf_armature

