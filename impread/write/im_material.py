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

from re import M
import bpy

from .dasar.g2b_material_helpers import get_gltf_node_name, create_settings_group
from .dasar.g2 import TextureInfo, MaterialPBRMetallicRoughness
from .dasar.g2_constants import GLTF_IOR
from .dasar.g2_binary import import_user_extensions
from .dasar.g2b_extras import set_extras
from .im_texture import texture

from .im_KHR_materials import(
    pbr_specular_glossiness,
    clearcoat,
    clearcoat_roughness,
    clearcoat_normal,
    transmission,
    ior, 
    volume,
    specular,
    sheen,
    anisotropy,
    MaterialHelper,
    pbr_metallic_roughness,
    make_output_nodes,
    base_color
    )
    
#----------------------------------------------------------------------
def unlit(mh):
    """Creates node tree for unlit materials."""
    # Emission node for the base color
    emission_node = mh.node_tree.nodes.new('ShaderNodeEmission')
    emission_node.location = 10, 126

    # Lightpath trick: makes Emission visible only to camera rays.
    # [Is Camera Ray] => [Mix] =>
    #   [Transparent] => [   ]
    #      [Emission] => [   ]
    lightpath_node = mh.node_tree.nodes.new('ShaderNodeLightPath')
    transparent_node = mh.node_tree.nodes.new('ShaderNodeBsdfTransparent')
    mix_node = mh.node_tree.nodes.new('ShaderNodeMixShader')
    lightpath_node.location = 10, 600
    transparent_node.location = 10, 240
    mix_node.location = 260, 320
    mh.node_tree.links.new(mix_node.inputs['Fac'], lightpath_node.outputs['Is Camera Ray'])
    mh.node_tree.links.new(mix_node.inputs[1], transparent_node.outputs[0])
    mh.node_tree.links.new(mix_node.inputs[2], emission_node.outputs[0])

    _emission_socket, alpha_socket, _ = make_output_nodes(
        mh,
        location=(420, 280) if mh.is_opaque() else (150, 130),
        additional_location=None, #No additional location needed for Unlit
        shader_socket=mix_node.outputs[0],
        make_emission_socket=False,
        make_alpha_socket=not mh.is_opaque(),
        make_volume_socket=None # Not possible to have KHR_materials_volume with unlit
    )

    base_color(
        mh,
        location=(-200, 380),
        color_socket=emission_node.inputs['Color'],
        alpha_socket=alpha_socket,
    )

#---------------------------------------------------------------

class BlenderMaterial():
    """Blender Material."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def create(gltf, material_idx, vertex_color):
        """Material creation."""
        pymaterial = gltf.data.materials[material_idx]

        import_user_extensions('gather_import_material_before_hook', gltf, pymaterial, vertex_color)

        name = pymaterial.name
        if name is None:
            name = "Material_" + str(material_idx)

        mat = bpy.data.materials.new(name)
        pymaterial.blender_material[vertex_color] = mat.name

        set_extras(mat, pymaterial.extras)
        BlenderMaterial.set_double_sided(pymaterial, mat)
        BlenderMaterial.set_alpha_mode(pymaterial, mat)
        BlenderMaterial.set_viewport_color(pymaterial, mat, vertex_color)

        mat.use_nodes = True
        while mat.node_tree.nodes:  # clear all nodes
            mat.node_tree.nodes.remove(mat.node_tree.nodes[0])

        mh = MaterialHelper(gltf, pymaterial, mat, vertex_color)

        exts = pymaterial.extensions or {}
        if 'KHR_materials_unlit' in exts:
            unlit(mh)
        elif 'KHR_materials_pbrSpecularGlossiness' in exts:
            pbr_specular_glossiness(mh)
        else:
            pbr_metallic_roughness(mh)

        # Manage KHR_materials_variants
        # We need to store link between material idx in glTF and Blender Material id
        if gltf.KHR_materials_variants is True:
            gltf.variant_mapping[str(material_idx) + str(vertex_color)] = mat

        import_user_extensions('gather_import_material_after_hook', gltf, pymaterial, vertex_color, mat)

    @staticmethod
    def set_double_sided(pymaterial, mat):
        mat.use_backface_culling = (pymaterial.double_sided != True)

    @staticmethod
    def set_alpha_mode(pymaterial, mat):
        alpha_mode = pymaterial.alpha_mode
        if alpha_mode == 'BLEND':
            mat.blend_method = 'BLEND'
        elif alpha_mode == 'MASK':
            mat.blend_method = 'CLIP'
            alpha_cutoff = pymaterial.alpha_cutoff
            alpha_cutoff = alpha_cutoff if alpha_cutoff is not None else 0.5
            mat.alpha_threshold = alpha_cutoff

    @staticmethod
    def set_viewport_color(pymaterial, mat, vertex_color):
        # If there is no texture and no vertex color, use the base color as
        # the color for the Solid view.
        if vertex_color:
            return

        exts = pymaterial.extensions or {}
        if 'KHR_materials_pbrSpecularGlossiness' in exts:
            # TODO
            return
        else:
            pbr = pymaterial.pbr_metallic_roughness
            if pbr is None or pbr.base_color_texture is not None:
                return
            color = pbr.base_color_factor or [1, 1, 1, 1]

        mat.diffuse_color = color
