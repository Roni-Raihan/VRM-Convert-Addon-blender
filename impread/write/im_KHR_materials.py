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
# Copyright 2018-2023 The glTF-Blender-IO authors.
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
import os
from typing import Optional, Tuple
import numpy as np
import tempfile
import enum
from .dasar.g2_constants import GLTF_IOR
from .dasar.g2 import TextureInfo, MaterialNormalTextureInfoClass
from .im_texture import texture
from .dasar.g2b_conversion import get_anisotropy_rotation_gltf_to_blender
from math import pi
from mathutils import Vector

#--------------------------------------------------------
class MaterialHelper:
    """Helper class. Stores material stuff to be passed around everywhere."""
    def __init__(self, gltf, pymat, mat, vertex_color):
        self.gltf = gltf
        self.pymat = pymat
        self.mat = mat
        self.node_tree = mat.node_tree
        self.vertex_color = vertex_color
        if pymat.pbr_metallic_roughness is None:
            pymat.pbr_metallic_roughness = \
                MaterialPBRMetallicRoughness.from_dict({})
        self.settings_node = None

    def is_opaque(self):
        alpha_mode = self.pymat.alpha_mode
        return alpha_mode is None or alpha_mode == 'OPAQUE'

    def needs_emissive(self):
        return (
            self.pymat.emissive_texture is not None or
            (self.pymat.emissive_factor or [0, 0, 0]) != [0, 0, 0]
        )


def pbr_metallic_roughness(mh: MaterialHelper):
    """Creates node tree for pbrMetallicRoughness materials."""
    pbr_node = mh.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    pbr_node.location = 10, 300
    additional_location = 40, -370 # For occlusion and/or volume / original PBR extensions

    # Set IOR to 1.5, this is the default in glTF
    # This value may be overridden later if IOR extension is set on file
    pbr_node.inputs['IOR'].default_value = GLTF_IOR

    if mh.pymat.occlusion_texture is not None:
        if mh.settings_node is None:
            mh.settings_node = make_settings_node(mh)
            mh.settings_node.location = additional_location
            mh.settings_node.width = 180
            additional_location = additional_location[0], additional_location[1] - 150

    need_volume_node = False
    if mh.pymat.extensions and 'KHR_materials_volume' in mh.pymat.extensions:
        if 'thicknessFactor' in mh.pymat.extensions['KHR_materials_volume'] \
            and mh.pymat.extensions['KHR_materials_volume']['thicknessFactor'] != 0.0:

            need_volume_node = True

            # We also need glTF Material Output Node, to set thicknessFactor and thicknessTexture
            if mh.settings_node is None:
                mh.settings_node = make_settings_node(mh)
                mh.settings_node.location = additional_location
                mh.settings_node.width = 180
                additional_location = additional_location[0], additional_location[1] - 150

    _, _, volume_socket  = make_output_nodes(
        mh,
        location=(250, 260),
        additional_location=additional_location,
        shader_socket=pbr_node.outputs[0],
        make_emission_socket=False, # is managed by Principled shader node
        make_alpha_socket=False, # is managed by Principled shader node
        make_volume_socket=need_volume_node
    )


    locs = calc_locations(mh)

    emission(
        mh,
        location=locs['emission'],
        color_socket=pbr_node.inputs['Emission Color'],
        strength_socket=pbr_node.inputs['Emission Strength'],
    )

    base_color(
        mh,
        location=locs['base_color'],
        color_socket=pbr_node.inputs['Base Color'],
        alpha_socket=pbr_node.inputs['Alpha'] if not mh.is_opaque() else None,
    )

    metallic_roughness(
        mh,
        location=locs['metallic_roughness'],
        metallic_socket=pbr_node.inputs['Metallic'],
        roughness_socket=pbr_node.inputs['Roughness'],
    )

    normal(
        mh,
        location=locs['normal'],
        normal_socket=pbr_node.inputs['Normal'],
    )

    if mh.pymat.occlusion_texture is not None:
        occlusion(
            mh,
            location=locs['occlusion'],
            occlusion_socket=mh.settings_node.inputs['Occlusion'],
        )

    clearcoat(
        mh,
        location=locs['clearcoat'],
        clearcoat_socket=pbr_node.inputs['Coat Weight'],
    )

    clearcoat_roughness(
        mh,
        location=locs['clearcoat_roughness'],
        roughness_socket=pbr_node.inputs['Coat Roughness'],
    )

    clearcoat_normal(
        mh,
        location=locs['clearcoat_normal'],
        normal_socket=pbr_node.inputs['Coat Normal'],
    )

    transmission(
        mh,
        location=locs['transmission'],
        transmission_socket=pbr_node.inputs['Transmission Weight']
    )

    if need_volume_node:
        volume(
            mh,
            location=locs['volume_thickness'],
            volume_socket=volume_socket,
            thickness_socket=mh.settings_node.inputs[1] if mh.settings_node else None
        )

    specular(
        mh,
        location_specular=locs['specularTexture'],
        location_specular_tint=locs['specularColorTexture'],
        specular_socket=pbr_node.inputs['Specular IOR Level'],
        specular_tint_socket=pbr_node.inputs['Specular Tint']
    )

    anisotropy(
        mh,
        location=locs['anisotropy'],
        anisotropy_socket=pbr_node.inputs['Anisotropic'],
        anisotropy_rotation_socket=pbr_node.inputs['Anisotropic Rotation'],
        anisotropy_tangent_socket=pbr_node.inputs['Tangent']
    )

    sheen(
        mh,
        location_sheenTint=locs['sheenColorTexture'],
        location_sheenRoughness=locs['sheenRoughnessTexture'],
        sheen_socket=pbr_node.inputs['Sheen Weight'],
        sheenTint_socket=pbr_node.inputs['Sheen Tint'],
        sheenRoughness_socket=pbr_node.inputs['Sheen Roughness']
    )

    ior(
        mh,
        ior_socket=pbr_node.inputs['IOR']
    )


def calc_locations(mh):
    """Calculate locations to place each bit of the node graph at."""
    # Lay the blocks out top-to-bottom, aligned on the right
    x = -200
    y = 0
    height = 460  # height of each block
    locs = {}

    try:
        clearcoat_ext = mh.pymat.extensions['KHR_materials_clearcoat']
    except Exception:
        clearcoat_ext = {}

    try:
        transmission_ext = mh.pymat.exntesions['KHR_materials_transmission']
    except:
        transmission_ext = {}

    try:
        volume_ext = mh.pymat.extensions['KHR_materials_volume']
    except Exception:
        volume_ext = {}

    try:
        specular_ext = mh.pymat.extensions['KHR_materials_specular']
    except:
        specular_ext = {}

    try:
        anisotropy_ext = mh.pymat.extensions['KHR_materials_anisotropy']
    except:
        anisotropy_ext = {}

    try:
        sheen_ext = mh.pymat.extensions['KHR_materials_sheen']
    except:
        sheen_ext = {}

    locs['base_color'] = (x, y)
    if mh.pymat.pbr_metallic_roughness.base_color_texture is not None or mh.vertex_color:
        y -= height
    locs['metallic_roughness'] = (x, y)
    if mh.pymat.pbr_metallic_roughness.metallic_roughness_texture is not None:
        y -= height
    locs['transmission'] = (x, y)
    if 'transmissionTexture' in transmission_ext:
        y -= height
    locs['normal'] = (x, y)
    if mh.pymat.normal_texture is not None:
        y -= height
    locs['specularTexture'] = (x, y)
    if 'specularTexture' in specular_ext:
        y -= height
    locs['specularColorTexture'] = (x, y)
    if 'specularColorTexture' in specular_ext:
        y -= height
    locs['anisotropy'] = (x, y)
    if 'anisotropyTexture' in anisotropy_ext:
        y -= height
    locs['sheenRoughnessTexture'] = (x, y)
    if 'sheenRoughnessTexture' in sheen_ext:
        y -= height
    locs['sheenColorTexture'] = (x, y)
    if 'sheenColorTexture' in sheen_ext:
        y -= height
    locs['clearcoat'] = (x, y)
    if 'clearcoatTexture' in clearcoat_ext:
        y -= height
    locs['clearcoat_roughness'] = (x, y)
    if 'clearcoatRoughnessTexture' in clearcoat_ext:
        y -= height
    locs['clearcoat_normal'] = (x, y)
    if 'clearcoatNormalTexture' in clearcoat_ext:
        y -= height
    locs['emission'] = (x, y)
    if mh.pymat.emissive_texture is not None:
        y -= height
    locs['occlusion'] = (x, y)
    if mh.pymat.occlusion_texture is not None:
        y -= height
    locs['volume_thickness'] = (x, y)
    if 'thicknessTexture' in volume_ext:
        y -= height

    # Center things
    total_height = -y
    y_offset = total_height / 2 - 20
    for key in locs:
        x, y = locs[key]
        locs[key] = (x, y + y_offset)

    return locs


# These functions each create one piece of the node graph, slotting
# their outputs into the given socket, or setting its default value.
# location is roughly the upper-right corner of where to put nodes.


# [Texture] => [Emissive Factor] =>
def emission(mh: MaterialHelper, location, color_socket, strength_socket):
    x, y = location
    emissive_factor = mh.pymat.emissive_factor or [0, 0, 0]

    strength = 1
    try:
        # Get strength from KHR_materials_emissive_strength if exists
        strength = mh.pymat.extensions['KHR_materials_emissive_strength']['emissiveStrength']
    except Exception:
        pass

    if color_socket is None:
        return

    if mh.pymat.emissive_texture is None:
        if emissive_factor == [0, 0, 0]:
            # Keep as close as possible to the default Blender value when there is no emission
            color_socket.default_value = [1,1,1,1]
            strength_socket.default_value = 0
            return
        color_socket.default_value = emissive_factor + [1]
        strength_socket.default_value = strength
        return

    # Put grayscale emissive factors into the Emission Strength
    e0, e1, e2 = emissive_factor
    if strength_socket and e0 == e1 == e2:
        strength_socket.default_value = e0 * strength

    # Otherwise, use a multiply node for it
    else:
        if emissive_factor != [1, 1, 1]:
            node = mh.node_tree.nodes.new('ShaderNodeMix')
            node.label = 'Emissive Factor'
            node.data_type = 'RGBA'
            node.location = x - 140, y
            node.blend_type = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(color_socket, node.outputs[2])
            # Inputs
            node.inputs['Factor'].default_value = 1.0
            color_socket = node.inputs[6]
            node.inputs[7].default_value = emissive_factor + [1]

            x -= 200

        strength_socket.default_value = strength

    texture(
        mh,
        tex_info=mh.pymat.emissive_texture,
        label='EMISSIVE',
        location=(x, y),
        color_socket=color_socket,
    )


#      [Texture] => [Mix Colors] => [Color Factor] =>
# [Vertex Color] => [Mix Alphas] => [Alpha Factor] =>
def base_color(
    mh: MaterialHelper,
    location,
    color_socket,
    alpha_socket=None,
    is_diffuse=False,
):
    """Handle base color (= baseColorTexture * vertexColor * baseColorFactor)."""
    x, y = location
    pbr = mh.pymat.pbr_metallic_roughness
    if not is_diffuse:
        base_color_factor = pbr.base_color_factor
        base_color_texture = pbr.base_color_texture
    else:
        # Handle pbrSpecularGlossiness's diffuse with this function too,
        # since it's almost exactly the same as base color.
        base_color_factor = \
            mh.pymat.extensions['KHR_materials_pbrSpecularGlossiness'] \
            .get('diffuseFactor', [1, 1, 1, 1])
        base_color_texture = \
            mh.pymat.extensions['KHR_materials_pbrSpecularGlossiness'] \
            .get('diffuseTexture', None)
        if base_color_texture is not None:
            base_color_texture = TextureInfo.from_dict(base_color_texture)

    if base_color_factor is None:
        base_color_factor = [1, 1, 1, 1]

    if base_color_texture is None and not mh.vertex_color:
        color_socket.default_value = base_color_factor[:3] + [1]
        if alpha_socket is not None:
            alpha_socket.default_value = base_color_factor[3]
        return

    # Mix in base color factor
    needs_color_factor = base_color_factor[:3] != [1, 1, 1]
    needs_alpha_factor = base_color_factor[3] != 1.0 and alpha_socket is not None
    if needs_color_factor or needs_alpha_factor:
        if needs_color_factor:
            node = mh.node_tree.nodes.new('ShaderNodeMix')
            node.label = 'Color Factor'
            node.data_type = "RGBA"
            node.location = x - 140, y
            node.blend_type = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(color_socket, node.outputs[2])
            # Inputs
            node.inputs['Factor'].default_value = 1.0
            color_socket = node.inputs[6]
            node.inputs[7].default_value = base_color_factor[:3] + [1]

        if needs_alpha_factor:
            node = mh.node_tree.nodes.new('ShaderNodeMath')
            node.label = 'Alpha Factor'
            node.location = x - 140, y - 200
            # Outputs
            mh.node_tree.links.new(alpha_socket, node.outputs[0])
            # Inputs
            node.operation = 'MULTIPLY'
            alpha_socket = node.inputs[0]
            node.inputs[1].default_value = base_color_factor[3]

        x -= 200

    # These are where the texture/vertex color node will put its output.
    texture_color_socket = color_socket
    texture_alpha_socket = alpha_socket
    vcolor_color_socket = color_socket
    vcolor_alpha_socket = alpha_socket

    # Mix texture and vertex color together
    if base_color_texture is not None and mh.vertex_color:
        node = mh.node_tree.nodes.new('ShaderNodeMix')
        node.label = 'Mix Vertex Color'
        node.data_type = 'RGBA'
        node.location = x - 140, y
        node.blend_type = 'MULTIPLY'
        # Outputs
        mh.node_tree.links.new(color_socket, node.outputs[2])
        # Inputs
        node.inputs['Factor'].default_value = 1.0
        texture_color_socket = node.inputs[6]
        vcolor_color_socket = node.inputs[7]

        if alpha_socket is not None:
            node = mh.node_tree.nodes.new('ShaderNodeMath')
            node.label = 'Mix Vertex Alpha'
            node.location = x - 140, y - 200
            node.operation = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(alpha_socket, node.outputs[0])
            # Inputs
            texture_alpha_socket = node.inputs[0]
            vcolor_alpha_socket = node.inputs[1]

        x -= 200

    # Vertex Color
    if mh.vertex_color:
        node = mh.node_tree.nodes.new('ShaderNodeVertexColor')
        # Do not set the layer name, so rendered one will be used (At import => The first one)
        node.location = x - 250, y - 240
        # Outputs
        mh.node_tree.links.new(vcolor_color_socket, node.outputs['Color'])
        if vcolor_alpha_socket is not None:
            mh.node_tree.links.new(vcolor_alpha_socket, node.outputs['Alpha'])

        x -= 280

    # Texture
    if base_color_texture is not None:
        texture(
            mh,
            tex_info=base_color_texture,
            label='BASE COLOR' if not is_diffuse else 'DIFFUSE',
            location=(x, y),
            color_socket=texture_color_socket,
            alpha_socket=texture_alpha_socket,
        )


# [Texture] => [Separate GB] => [Metal/Rough Factor] =>
def metallic_roughness(mh: MaterialHelper, location, metallic_socket, roughness_socket):
    x, y = location
    pbr = mh.pymat.pbr_metallic_roughness
    metal_factor = pbr.metallic_factor
    rough_factor = pbr.roughness_factor
    if metal_factor is None:
        metal_factor = 1.0
    if rough_factor is None:
        rough_factor = 1.0

    if pbr.metallic_roughness_texture is None:
        metallic_socket.default_value = metal_factor
        roughness_socket.default_value = rough_factor
        return

    if metal_factor != 1.0 or rough_factor != 1.0:
        # Mix metal factor
        if metal_factor != 1.0:
            node = mh.node_tree.nodes.new('ShaderNodeMath')
            node.label = 'Metallic Factor'
            node.location = x - 140, y
            node.operation = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(metallic_socket, node.outputs[0])
            # Inputs
            metallic_socket = node.inputs[0]
            node.inputs[1].default_value = metal_factor

        # Mix rough factor
        if rough_factor != 1.0:
            node = mh.node_tree.nodes.new('ShaderNodeMath')
            node.label = 'Roughness Factor'
            node.location = x - 140, y - 200
            node.operation = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(roughness_socket, node.outputs[0])
            # Inputs
            roughness_socket = node.inputs[0]
            node.inputs[1].default_value = rough_factor

        x -= 200

    # Separate RGB
    node = mh.node_tree.nodes.new('ShaderNodeSeparateColor')
    node.location = x - 150, y - 75
    # Outputs
    mh.node_tree.links.new(metallic_socket, node.outputs['Blue'])
    mh.node_tree.links.new(roughness_socket, node.outputs['Green'])
    # Inputs
    color_socket = node.inputs[0]

    x -= 200

    texture(
        mh,
        tex_info=pbr.metallic_roughness_texture,
        label='METALLIC ROUGHNESS',
        location=(x, y),
        is_data=True,
        color_socket=color_socket,
    )


# [Texture] => [Normal Map] =>
def normal(mh: MaterialHelper, location, normal_socket):
    x,y = location
    tex_info = mh.pymat.normal_texture

    if tex_info is None:
        return

    # Normal map
    node = mh.node_tree.nodes.new('ShaderNodeNormalMap')
    node.location = x - 150, y - 40
    # Set UVMap
    uv_idx = tex_info.tex_coord or 0
    try:
        uv_idx = tex_info.extensions['KHR_texture_transform']['texCoord']
    except Exception:
        pass
    node.uv_map = 'UVMap' if uv_idx == 0 else 'UVMap.%03d' % uv_idx
    # Set strength
    scale = tex_info.scale
    scale = scale if scale is not None else 1
    node.inputs['Strength'].default_value = scale
    # Outputs
    mh.node_tree.links.new(normal_socket, node.outputs['Normal'])
    # Inputs
    color_socket = node.inputs['Color']

    x -= 200

    texture(
        mh,
        tex_info=tex_info,
        label='NORMALMAP',
        location=(x, y),
        is_data=True,
        color_socket=color_socket,
    )


# [Texture] => [Separate R] => [Mix Strength] =>
def occlusion(mh: MaterialHelper, location, occlusion_socket):
    x, y = location

    if mh.pymat.occlusion_texture is None:
        return

    strength = mh.pymat.occlusion_texture.strength
    if strength is None: strength = 1.0
    if strength != 1.0:
        # Mix with white
        node = mh.node_tree.nodes.new('ShaderNodeMix')
        node.label = 'Occlusion Strength'
        node.data_type = 'RGBA'
        node.location = x - 140, y
        node.blend_type = 'MIX'
        # Outputs
        mh.node_tree.links.new(occlusion_socket, node.outputs[0])
        # Inputs
        node.inputs['Factor'].default_value = strength
        node.inputs[6].default_value = [1, 1, 1, 1]
        occlusion_socket = node.inputs[7]

        x -= 200

    # Separate RGB
    node = mh.node_tree.nodes.new('ShaderNodeSeparateColor')
    node.location = x - 150, y - 75
    # Outputs
    mh.node_tree.links.new(occlusion_socket, node.outputs['Red'])
    # Inputs
    color_socket = node.inputs[0]

    x -= 200

    texture(
        mh,
        tex_info=mh.pymat.occlusion_texture,
        label='OCCLUSION',
        location=(x, y),
        is_data=True,
        color_socket=color_socket,
    )


# => [Add Emission] => [Mix Alpha] => [Material Output] if needed, only for SpecGlossiness
# => [Volume] => [Add Shader] => [Material Output] if needed
# => [Sheen] => [Add Shader] => [Material Output] if needed
def make_output_nodes(
    mh: MaterialHelper,
    location,
    additional_location,
    shader_socket,
    make_emission_socket,
    make_alpha_socket,
    make_volume_socket
):
    """
    Creates the Material Output node and connects shader_socket to it.
    If requested, it can also create places to hookup the emission/alpha
    in between shader_socket and the Output node too.

    :return: a pair containing the sockets you should put emission and alpha
    in (None if not requested).
    """
    x, y = location
    emission_socket = None
    alpha_socket = None

    # Create an Emission node and add it to the shader.
    if make_emission_socket:
        # Emission
        node = mh.node_tree.nodes.new('ShaderNodeEmission')
        node.location = x + 50, y + 250
        # Inputs
        emission_socket = node.inputs[0]
        # Outputs
        emission_output = node.outputs[0]

        # Add
        node = mh.node_tree.nodes.new('ShaderNodeAddShader')
        node.location = x + 250, y + 160
        # Inputs
        mh.node_tree.links.new(node.inputs[0], emission_output)
        mh.node_tree.links.new(node.inputs[1], shader_socket)
        # Outputs
        shader_socket = node.outputs[0]

        if make_alpha_socket:
            x += 200
            y += 175
        else:
            x += 380
            y += 125

    # Mix with a Transparent BSDF. Mixing factor is the alpha value.
    if make_alpha_socket:
        # Transparent BSDF
        node = mh.node_tree.nodes.new('ShaderNodeBsdfTransparent')
        node.location = x + 100, y - 350
        # Outputs
        transparent_out = node.outputs[0]

        # Mix
        node = mh.node_tree.nodes.new('ShaderNodeMixShader')
        node.location = x + 340, y - 180
        # Inputs
        alpha_socket = node.inputs[0]
        mh.node_tree.links.new(node.inputs[1], transparent_out)
        mh.node_tree.links.new(node.inputs[2], shader_socket)
        # Outputs
        shader_socket = node.outputs[0]


        x += 480
        y -= 210

    # Material output
    node_output = mh.node_tree.nodes.new('ShaderNodeOutputMaterial')
    node_output.location = x + 70, y + 10

    # Outputs
    mh.node_tree.links.new(node_output.inputs[0], shader_socket)

    # Volume Node
    volume_socket = None
    if make_volume_socket:
        node = mh.node_tree.nodes.new('ShaderNodeVolumeAbsorption')
        node.location = additional_location
        # Outputs
        mh.node_tree.links.new(node_output.inputs[1], node.outputs[0])
        volume_socket = node.outputs[0]


    return emission_socket, alpha_socket, volume_socket


def make_settings_node(mh):
    """
    Make a Group node with a hookup for Occlusion. No effect in Blender, but
    used to tell the exporter what the occlusion map should be.
    """
    node = mh.node_tree.nodes.new('ShaderNodeGroup')
    node.node_tree = get_settings_group()
    return node

def get_settings_group():
    gltf_node_group_name = get_gltf_node_name()
    if gltf_node_group_name in bpy.data.node_groups:
        gltf_node_group = bpy.data.node_groups[gltf_node_group_name]
    else:
        # Create a new node group
        gltf_node_group = create_settings_group(gltf_node_group_name)
    return gltf_node_group

#------------------------------------------------------------------------
def volume(mh, location, volume_socket, thickness_socket):
    # implementation based on https://github.com/KhronosGroup/glTF-Blender-IO/issues/1454#issuecomment-928319444
    try:
        ext = mh.pymat.extensions['KHR_materials_volume']
    except Exception:
        return

    # Attenuation Color
    attenuationColor = \
            mh.pymat.extensions['KHR_materials_volume'] \
            .get('attenuationColor')
    # glTF is color3, Blender adds alpha
    if attenuationColor is None:
        attenuationColor = [1.0, 1.0, 1.0, 1.0]
    else:
        attenuationColor.extend([1.0])
    volume_socket.node.inputs[0].default_value = attenuationColor

    # Attenuation Distance / Density
    attenuationDistance = mh.pymat.extensions['KHR_materials_volume'].get('attenuationDistance')
    if attenuationDistance is None:
        density = 0
    else:
        density = 1.0 / attenuationDistance
    volume_socket.node.inputs[1].default_value = density

    # thicknessFactor / thicknessTexture
    x, y = location
    try:
        ext = mh.pymat.extensions['KHR_materials_volume']
    except Exception:
        return
    thickness_factor = ext.get('thicknessFactor', 0)
    tex_info = ext.get('thicknessTexture')
    if tex_info is not None:
        tex_info = TextureInfo.from_dict(tex_info)

    if thickness_socket is None:
        return

    if tex_info is None:
        thickness_socket.default_value = thickness_factor
        return

    # Mix thickness factor
    if thickness_factor != 1:
        node = mh.node_tree.nodes.new('ShaderNodeMath')
        node.label = 'Thickness Factor'
        node.location = x - 140, y
        node.operation = 'MULTIPLY'
        # Outputs
        mh.node_tree.links.new(thickness_socket, node.outputs[0])
        # Inputs
        thickness_socket = node.inputs[0]
        node.inputs[1].default_value = thickness_factor

        x -= 200

    # Separate RGB
    node = mh.node_tree.nodes.new('ShaderNodeSeparateColor')
    node.location = x - 150, y - 75
    # Outputs
    mh.node_tree.links.new(thickness_socket, node.outputs['Green'])
    # Inputs
    thickness_socket = node.inputs[0]

    x -= 200

    texture(
        mh,
        tex_info=tex_info,
        label='THICKNESS',
        location=(x, y),
        is_data=True,
        color_socket=thickness_socket,
    )

#------------------------------------------------------------------------
# [Texture] => [Separate R] => [Transmission Factor] =>
def transmission(mh, location, transmission_socket):
    x, y = location
    try:
        ext = mh.pymat.extensions['KHR_materials_transmission']
    except Exception:
        return
    transmission_factor = ext.get('transmissionFactor', 0)

    # Default value is 0, so no transmission
    if transmission_factor == 0:
        return

    # Activate screen refraction (for Eevee)
    mh.mat.use_screen_refraction = True

    tex_info = ext.get('transmissionTexture')
    if tex_info is not None:
        tex_info = TextureInfo.from_dict(tex_info)

    if transmission_socket is None:
        return

    if tex_info is None:
        transmission_socket.default_value = transmission_factor
        return

    # Mix transmission factor
    if transmission_factor != 1:
        node = mh.node_tree.nodes.new('ShaderNodeMath')
        node.label = 'Transmission Factor'
        node.location = x - 140, y
        node.operation = 'MULTIPLY'
        # Outputs
        mh.node_tree.links.new(transmission_socket, node.outputs[0])
        # Inputs
        transmission_socket = node.inputs[0]
        node.inputs[1].default_value = transmission_factor

        x -= 200

    # Separate RGB
    node = mh.node_tree.nodes.new('ShaderNodeSeparateColor')
    node.location = x - 150, y - 75
    # Outputs
    mh.node_tree.links.new(transmission_socket, node.outputs['Red'])
    # Inputs
    transmission_socket = node.inputs[0]

    x -= 200

    texture(
        mh,
        tex_info=tex_info,
        label='TRANSMISSION',
        location=(x, y),
        is_data=True,
        color_socket=transmission_socket,
    )

#-------------------------------------------------------------------------
class Channel(enum.IntEnum):
    R = 0
    G = 1
    B = 2
    A = 3

class TmpImageGuard:
    """Guard to automatically clean up temp images (use it with `with`)."""
    def __init__(self):
        self.image = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.image is not None:
            bpy.data.images.remove(self.image, do_unlink=True)

def make_temp_image_copy(guard: TmpImageGuard, src_image: bpy.types.Image):
    """Makes a temporary copy of src_image. Will be cleaned up with guard."""
    guard.image = src_image.copy()
    tmp_image = guard.image

    tmp_image.update()
    # See #1564 and T95616
    tmp_image.scale(*src_image.size)

    if src_image.is_dirty: # Warning, img size change doesn't make it dirty, see T95616
        # Unsaved changes aren't copied by .copy(), so do them ourselves
        tmp_buf = np.empty(src_image.size[0] * src_image.size[1] * 4, np.float32)
        src_image.pixels.foreach_get(tmp_buf)
        tmp_image.pixels.foreach_set(tmp_buf)


def specular(mh, location_specular,
                 location_specular_tint,
                 specular_socket,
                 specular_tint_socket):

    if specular_socket is None:
        return
    if specular_tint_socket is None:
        return

    try:
        ext = mh.pymat.extensions['KHR_materials_specular']
    except Exception:
        return

    # First check if we need a texture or not -> retrieve all info needed
    specular_factor = ext.get('specularFactor', 1.0)
    tex_specular_info = ext.get('specularTexture')
    if tex_specular_info is not None:
        tex_specular_info = TextureInfo.from_dict(tex_specular_info)

    specular_tint_factor = ext.get('specularColorFactor', [1.0, 1.0, 1.0])[:3]
    tex_specular_tint_info = ext.get('specularColorTexture')
    if tex_specular_tint_info is not None:
        tex_specular_tint_info = TextureInfo.from_dict(tex_specular_tint_info)

    x_specular, y_specular = location_specular
    x_specularcolor, y_specularcolor = location_specular_tint

    if tex_specular_info is None:
        specular_socket.default_value = specular_factor / 2.0
    else:
        # Mix specular factor
        if specular_factor != 1.0:
            node = mh.node_tree.nodes.new('ShaderNodeMath')
            node.label = 'Specular Factor'
            node.location = x_specular - 140, y_specular
            node.operation = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(specular_socket, node.outputs[0])
            # Inputs
            specular_socket = node.inputs[0]
            node.inputs[1].default_value = specular_factor / 2.0
            x_specular -= 200

        texture(
            mh,
            tex_info=tex_specular_info,
            label='SPECULAR',
            location=(x_specular, y_specular),
            is_data=True,
            color_socket=None,
            alpha_socket=specular_socket
            )

    if tex_specular_tint_info is None:
        specular_tint_factor = list(specular_tint_factor)
        specular_tint_factor.extend([1.0])
        specular_tint_socket.default_value = specular_tint_factor
    else:
            specular_tint_factor = list(specular_tint_factor) + [1.0]
            if specular_tint_factor != [1.0, 1.0, 1.0, 1.0]:
                # Mix specularColorFactor
                node = mh.node_tree.nodes.new('ShaderNodeMix')
                node.label = 'SpecularColor Factor'
                node.data_type = 'RGBA'
                node.location = x_specularcolor - 140, y_specularcolor
                node.blend_type = 'MULTIPLY'
                # Outputs
                mh.node_tree.links.new(specular_tint_socket, node.outputs[2])
                # Inputs
                node.inputs['Factor'].default_value = 1.0
                specular_tint_socket = node.inputs[6]
                node.inputs[7].default_value = specular_tint_factor
                x_specularcolor -= 200

            texture(
                mh,
                tex_info=tex_specular_tint_info,
                label='SPECULAR COLOR',
                location=(x_specularcolor, y_specularcolor),
                color_socket=specular_tint_socket,
                )

#------------------------------------------------------------------------
def sheen(  mh,
            location_sheenTint,
            location_sheenRoughness,
            sheen_socket,
            sheenTint_socket,
            sheenRoughness_socket
            ):

    x_sheenTint, y_sheenTint = location_sheenTint
    x_sheenRoughness, y_sheenRoughness = location_sheenRoughness

    try:
        ext = mh.pymat.extensions['KHR_materials_sheen']
    except Exception:
        return

    sheen_socket.default_value = 1.0
    sheenTintFactor = ext.get('sheenColorFactor', [0.0, 0.0, 0.0])
    tex_info_color = ext.get('sheenColorTexture')
    if tex_info_color is not None:
        tex_info_color = TextureInfo.from_dict(tex_info_color)

    sheenRoughnessFactor = ext.get('sheenRoughnessFactor', 0.0)
    tex_info_roughness = ext.get('sheenRoughnessTexture')
    if tex_info_roughness is not None:
        tex_info_roughness = TextureInfo.from_dict(tex_info_roughness)

    if tex_info_color is None:
        sheenTintFactor.extend([1.0])
        sheenTint_socket.default_value = sheenTintFactor
    else:
        # Mix sheenTint factor
        sheenTintFactor = sheenTintFactor + [1.0]
        if sheenTintFactor != [1.0, 1.0, 1.0, 1.0]:
            node = mh.node_tree.nodes.new('ShaderNodeMix')
            node.label = 'sheenTint Factor'
            node.data_type = 'RGBA'
            node.location = x_sheenTint - 140, y_sheenTint
            node.blend_type = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(sheenTint_socket, node.outputs[2])
            # Inputs
            node.inputs['Factor'].default_value = 1.0
            sheenTint_socket = node.inputs[6]
            node.inputs[7].default_value = sheenTintFactor
            x_sheenTint -= 200

        texture(
            mh,
            tex_info=tex_info_color,
            label='SHEEN COLOR',
            location=(x_sheenTint, y_sheenTint),
            color_socket=sheenTint_socket
            )

    if tex_info_roughness is None:
        sheenRoughness_socket.default_value = sheenRoughnessFactor
    else:
         # Mix sheenRoughness factor
        if sheenRoughnessFactor != 1.0:
            node = mh.node_tree.nodes.new('ShaderNodeMath')
            node.label = 'shennRoughness Factor'
            node.location = x_sheenRoughness - 140, y_sheenRoughness
            node.operation = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(sheenRoughness_socket, node.outputs[0])
            # Inputs
            sheenRoughness_socket = node.inputs[0]
            node.inputs[1].default_value = sheenRoughnessFactor
            x_sheenRoughness -= 200

        texture(
            mh,
            tex_info=tex_info_roughness,
            label='SHEEN ROUGHNESS',
            location=(x_sheenRoughness, y_sheenRoughness),
            is_data=True,
            color_socket=None,
            alpha_socket=sheenRoughness_socket
            )
    return

#---------------------------------------------------------------------
# [Texture] => [Separate R] => [Clearcoat Factor] =>
def clearcoat(mh, location, clearcoat_socket):
    x, y = location
    try:
        ext = mh.pymat.extensions['KHR_materials_clearcoat']
    except Exception:
        return
    clearcoat_factor = ext.get('clearcoatFactor', 0)
    tex_info = ext.get('clearcoatTexture')
    if tex_info is not None:
        tex_info = TextureInfo.from_dict(tex_info)

    if clearcoat_socket is None:
        return

    if tex_info is None:
        clearcoat_socket.default_value = clearcoat_factor
        return

    # Mix clearcoat factor
    if clearcoat_factor != 1:
        node = mh.node_tree.nodes.new('ShaderNodeMath')
        node.label = 'Clearcoat Factor'
        node.location = x - 140, y
        node.operation = 'MULTIPLY'
        # Outputs
        mh.node_tree.links.new(clearcoat_socket, node.outputs[0])
        # Inputs
        clearcoat_socket = node.inputs[0]
        node.inputs[1].default_value = clearcoat_factor

        x -= 200

    # Separate RGB
    node = mh.node_tree.nodes.new('ShaderNodeSeparateColor')
    node.location = x - 150, y - 75
    # Outputs
    mh.node_tree.links.new(clearcoat_socket, node.outputs['Red'])
    # Inputs
    clearcoat_socket = node.inputs[0]

    x -= 200

    texture(
        mh,
        tex_info=tex_info,
        label='CLEARCOAT',
        location=(x, y),
        is_data=True,
        color_socket=clearcoat_socket,
    )


# [Texture] => [Separate G] => [Roughness Factor] =>
def clearcoat_roughness(mh, location, roughness_socket):
    x, y = location
    try:
        ext = mh.pymat.extensions['KHR_materials_clearcoat']
    except Exception:
        return
    roughness_factor = ext.get('clearcoatRoughnessFactor', 0)
    tex_info = ext.get('clearcoatRoughnessTexture')
    if tex_info is not None:
        tex_info = TextureInfo.from_dict(tex_info)

    if roughness_socket is None:
        return

    if tex_info is None:
        roughness_socket.default_value = roughness_factor
        return

    # Mix roughness factor
    if roughness_factor != 1:
        node = mh.node_tree.nodes.new('ShaderNodeMath')
        node.label = 'Clearcoat Roughness Factor'
        node.location = x - 140, y
        node.operation = 'MULTIPLY'
        # Outputs
        mh.node_tree.links.new(roughness_socket, node.outputs[0])
        # Inputs
        roughness_socket = node.inputs[0]
        node.inputs[1].default_value = roughness_factor

        x -= 200

    # Separate RGB (roughness is in G)
    node = mh.node_tree.nodes.new('ShaderNodeSeparateColor')
    node.location = x - 150, y - 75
    # Outputs
    mh.node_tree.links.new(roughness_socket, node.outputs['Green'])
    # Inputs
    color_socket = node.inputs[0]

    x -= 200

    texture(
        mh,
        tex_info=tex_info,
        label='CLEARCOAT ROUGHNESS',
        location=(x, y),
        is_data=True,
        color_socket=color_socket,
    )


# [Texture] => [Normal Map] =>
def clearcoat_normal(mh, location, normal_socket):
    x,y = location
    try:
        ext = mh.pymat.extensions['KHR_materials_clearcoat']
    except Exception:
        return
    tex_info = ext.get('clearcoatNormalTexture')
    if tex_info is not None:
        tex_info = MaterialNormalTextureInfoClass.from_dict(tex_info)

    if tex_info is None:
        return

    # Normal map
    node = mh.node_tree.nodes.new('ShaderNodeNormalMap')
    node.location = x - 150, y - 40
    # Set UVMap
    uv_idx = tex_info.tex_coord or 0
    try:
        uv_idx = tex_info.extensions['KHR_texture_transform']['texCoord']
    except Exception:
        pass
    node.uv_map = 'UVMap' if uv_idx == 0 else 'UVMap.%03d' % uv_idx
    # Set strength
    scale = tex_info.scale
    scale = scale if scale is not None else 1
    node.inputs['Strength'].default_value = scale
    # Outputs
    mh.node_tree.links.new(normal_socket, node.outputs['Normal'])
    # Inputs
    color_socket = node.inputs['Color']

    x -= 200

    texture(
        mh,
        tex_info=tex_info,
        label='CLEARCOAT NORMAL',
        location=(x, y),
        is_data=True,
        color_socket=color_socket,
    )

#-----------------------------------------------------------------------
def pbr_specular_glossiness(mh):
    """Creates node tree for pbrSpecularGlossiness materials."""
    # This does option #1 from
    # https://github.com/KhronosGroup/glTF-Blender-IO/issues/303

    # Sum a Glossy and Diffuse Shader
    glossy_node = mh.node_tree.nodes.new('ShaderNodeBsdfGlossy')
    diffuse_node = mh.node_tree.nodes.new('ShaderNodeBsdfDiffuse')
    add_node = mh.node_tree.nodes.new('ShaderNodeAddShader')
    glossy_node.location = 10, 220
    diffuse_node.location = 10, 0
    add_node.location = 230, 100
    mh.node_tree.links.new(add_node.inputs[0], glossy_node.outputs[0])
    mh.node_tree.links.new(add_node.inputs[1], diffuse_node.outputs[0])

    emission_socket, alpha_socket, _ = make_output_nodes(
        mh,
        location=(370, 250),
        additional_location=None, #No additional location needed for SpecGloss
        shader_socket=add_node.outputs[0],
        make_emission_socket=mh.needs_emissive(),
        make_alpha_socket=not mh.is_opaque(),
        make_volume_socket=None # No possible to have KHR_materials_volume with specular/glossiness
    )

    if emission_socket:
        emission(
            mh,
            location=(-200, 860),
            color_socket=emission_socket,
            strength_socket=emission_socket.node.inputs['Strength']
        )

    base_color(
        mh,
        is_diffuse=True,
        location=(-200, 380),
        color_socket=diffuse_node.inputs['Color'],
        alpha_socket=alpha_socket,
    )

    specular_glossiness(
        mh,
        location=(-200, -100),
        specular_socket=glossy_node.inputs['Color'],
        roughness_socket=glossy_node.inputs['Roughness'],
    )
    copy_socket(
        mh,
        copy_from=glossy_node.inputs['Roughness'],
        copy_to=diffuse_node.inputs['Roughness'],
    )

    normal(
        mh,
        location=(-200, -580),
        normal_socket=glossy_node.inputs['Normal'],
    )
    copy_socket(
        mh,
        copy_from=glossy_node.inputs['Normal'],
        copy_to=diffuse_node.inputs['Normal'],
    )

    if mh.pymat.occlusion_texture is not None:
        if mh.settings_node is None:
            mh.settings_node = make_settings_node(mh)
            mh.settings_node.location = (610, -1060)
        occlusion(
            mh,
            location=(510, -970),
            occlusion_socket=mh.settings_node.inputs['Occlusion'],
        )


# [Texture] => [Spec/Gloss Factor] => [Gloss to Rough] =>
def specular_glossiness(mh, location, specular_socket, roughness_socket):
    x, y = location
    spec_factor = mh.pymat.extensions \
        ['KHR_materials_pbrSpecularGlossiness'] \
        .get('specularFactor', [1, 1, 1])
    gloss_factor = mh.pymat.extensions \
        ['KHR_materials_pbrSpecularGlossiness'] \
        .get('glossinessFactor', 1)
    spec_gloss_texture = mh.pymat.extensions \
        ['KHR_materials_pbrSpecularGlossiness'] \
        .get('specularGlossinessTexture', None)
    if spec_gloss_texture is not None:
        spec_gloss_texture = TextureInfo.from_dict(spec_gloss_texture)

    if spec_gloss_texture is None:
        specular_socket.default_value = spec_factor + [1]
        roughness_socket.default_value = 1 - gloss_factor
        return

    # (1 - x) converts glossiness to roughness
    node = mh.node_tree.nodes.new('ShaderNodeInvert')
    node.label = 'Invert (Gloss to Rough)'
    node.location = x - 140, y - 75
    # Outputs
    mh.node_tree.links.new(roughness_socket, node.outputs[0])
    # Inputs
    node.inputs['Fac'].default_value = 1
    glossiness_socket = node.inputs['Color']

    x -= 250

    # Mix in spec/gloss factor
    if spec_factor != [1, 1, 1] or gloss_factor != 1:
        if spec_factor != [1, 1, 1]:
            node = mh.node_tree.nodes.new('ShaderNodeMix')
            node.data_type = 'RGBA'
            node.label = 'Specular Factor'
            node.location = x - 140, y
            node.blend_type = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(specular_socket, node.outputs[2])
            # Inputs
            node.inputs['Factor'].default_value = 1.0
            specular_socket = node.inputs[6]
            node.inputs[7].default_value = spec_factor + [1]

        if gloss_factor != 1:
            node = mh.node_tree.nodes.new('ShaderNodeMath')
            node.label = 'Glossiness Factor'
            node.location = x - 140, y - 200
            node.operation = 'MULTIPLY'
            # Outputs
            mh.node_tree.links.new(glossiness_socket, node.outputs[0])
            # Inputs
            glossiness_socket = node.inputs[0]
            node.inputs[1].default_value = gloss_factor

        x -= 200

    texture(
        mh,
        tex_info=spec_gloss_texture,
        label='SPECULAR GLOSSINESS',
        location=(x, y),
        color_socket=specular_socket,
        alpha_socket=glossiness_socket,
    )


def copy_socket(mh, copy_from, copy_to):
    """Copy the links/default value from one socket to another."""
    copy_to.default_value = copy_from.default_value
    for link in copy_from.links:
        mh.node_tree.links.new(copy_to, link.from_socket)

#--------------------------------------------------------------
def anisotropy(
        mh,
        location,
        anisotropy_socket,
        anisotropy_rotation_socket,
        anisotropy_tangent_socket
        ):

    if anisotropy_socket is None or anisotropy_rotation_socket is None or anisotropy_tangent_socket is None:
        return

    x, y = location
    try:
        ext = mh.pymat.extensions['KHR_materials_anisotropy']
    except Exception:
        return

    anisotropy_strength = ext.get('anisotropyStrength', 0)
    anisotropy_rotation = ext.get('anisotropyRotation', 0)
    tex_info = ext.get('anisotropyTexture')
    if tex_info is not None:
        tex_info = TextureInfo.from_dict(tex_info)


    # We are going to use UVMap of Normal map if it exists, as input for the anisotropy tangent


    if tex_info is None:
        anisotropy_socket.default_value = anisotropy_strength
        anisotropy_rotation_socket.default_value = get_anisotropy_rotation_gltf_to_blender(anisotropy_rotation)
        return

    # Tangent node
    node = mh.node_tree.nodes.new('ShaderNodeTangent')
    node.direction_type = "UV_MAP"
    node.location = x - 180, y - 200
    uv_idx = tex_info.tex_coord or 0

    # Get the UVMap of the normal map if available (if not, keeping the first UVMap available, uv_idx = 0)
    tex_info_normal = mh.pymat.normal_texture
    if tex_info_normal is not None:
        try:
            uv_idx = tex_info.extensions['KHR_texture_transform']['texCoord']
        except Exception:
            pass

    node.uv_map = 'UVMap' if uv_idx == 0 else 'UVMap.%03d' % uv_idx
    mh.node_tree.links.new(anisotropy_tangent_socket, node.outputs['Tangent'])


    # Multiply node
    multiply_node = mh.node_tree.nodes.new('ShaderNodeMath')
    multiply_node.label = 'Anisotropy strength'
    multiply_node.operation = 'MULTIPLY'
    multiply_node.location = x - 180, y + 200
    mh.node_tree.links.new(anisotropy_socket, multiply_node.outputs[0])
    multiply_node.inputs[1].default_value = anisotropy_strength

    # Divide node
    divide_node = mh.node_tree.nodes.new('ShaderNodeMath')
    divide_node.label = 'Rotation conversion'
    divide_node.operation = 'DIVIDE'
    divide_node.location = x - 180, y
    mh.node_tree.links.new(anisotropy_rotation_socket, divide_node.outputs[0])
    divide_node.inputs[1].default_value = 2 * pi

    # Rotation node
    rotation_node = mh.node_tree.nodes.new('ShaderNodeMath')
    rotation_node.label = 'Anisotropy rotation'
    rotation_node.operation = 'ADD'
    rotation_node.location = x - 180*2, y
    mh.node_tree.links.new(divide_node.inputs[0], rotation_node.outputs[0])
    rotation_node.inputs[1].default_value = anisotropy_rotation

    # ArcTan node
    arctan_node = mh.node_tree.nodes.new('ShaderNodeMath')
    arctan_node.label = 'ArcTan2'
    arctan_node.operation = 'ARCTAN2'
    arctan_node.location = x - 180*3, y
    mh.node_tree.links.new(rotation_node.inputs[0], arctan_node.outputs[0])

    # Separate XYZ
    sep_node = mh.node_tree.nodes.new('ShaderNodeSeparateXYZ')
    sep_node.location = x - 180*4, y
    mh.node_tree.links.new(arctan_node.inputs[0], sep_node.outputs[1])
    mh.node_tree.links.new(arctan_node.inputs[1], sep_node.outputs[0])
    mh.node_tree.links.new(multiply_node.inputs[0], sep_node.outputs[2])

    # Multiply add node
    multiply_add_node = mh.node_tree.nodes.new('ShaderNodeVectorMath')
    multiply_add_node.location = x - 180*5, y
    multiply_add_node.operation = 'MULTIPLY_ADD'
    multiply_add_node.inputs[1].default_value = Vector((2, 2, 1))
    multiply_add_node.inputs[2].default_value = Vector((-1, -1, 0))
    mh.node_tree.links.new(sep_node.inputs[0], multiply_add_node.outputs[0])

    # Texture
    texture(
        mh,
        tex_info=tex_info,
        label='ANISOTROPY',
        location=(x - 180*6, y),
        is_data=True,
        color_socket=multiply_add_node.inputs[0]
        )

#------------------------------------------------------
def ior(mh, ior_socket):
    try:
        ext = mh.pymat.extensions['KHR_materials_ior']
    except Exception:
        return
    ior = ext.get('ior', GLTF_IOR)
    ior_socket.default_value = ior
