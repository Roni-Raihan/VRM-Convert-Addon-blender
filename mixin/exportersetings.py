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


import bpy
import mathutils  

import os

from .dasar.collections import get_object_collection
from .dasar.material import get_root_node, get_from_node
from .dasar.vertex import uv_equals, normal_equals
from .dasar.objects import (
    get_object_properties, is_collision, is_object_visible,
    set_active_object)

#-----
class GeomMixin(object):
    pass

#------
class MaterialMixin(object):
    def get_metallic(self, material, shader):
        if shader.type in ('BSDF_GLASS', 'BSDF_ANISOTROPIC'):
            return 1

        # Math [Value] -> [Metallic] Principled BSDF
        # math_node = get_from_node(
        #     material.node_tree, 'MATH', to_node=shader,
        #     from_socket_name='Value', to_socket_name='Metallic')
        # if math_node:
        #     for input_ in math_node.inputs:
        #         if input_.name == 'Value' and not input_.is_linked:
        #             if input_.default_value < 0.5:
        #                 return 0
        #             else:
        #                 return 1

        # elif not shader.inputs['Metallic'].is_linked:
        #     return shader.inputs['Metallic'].default_value

        if shader.inputs['Metallic'].is_linked:
            return 0  # metallic map is not supported in RP -> disable
        else:
            return shader.inputs['Metallic'].default_value

    def get_roughness(self, material, shader):
        # Math [Value] -> [Roughness] Principled BSDF
        math_node = get_from_node(
            material.node_tree, 'MATH', to_node=shader,
            from_socket_name='Value', to_socket_name='Roughness')
        if math_node:
            for input_ in math_node.inputs:
                if input_.name == 'Value' and not input_.is_linked:
                    return input_.default_value
        else:
            return shader.inputs['Roughness'].default_value

    def get_emission(self, material, shader):
        # if not shader.inputs['Emission'].is_linked and not shader.inputs['Emission Strength'].is_linked:
        #     r, g, b, *_ = shader.inputs['Emission'].default_value
        #     e = shader.inputs['Emission Strength'].default_value
        #     return (r * e, g * e, b * e)

        # Mix RGB [Color] -> [Emission] Principled BSDF
        
        mix_node = get_from_node(
            material.node_tree, 'MIX_RGB', to_node=shader,
            from_socket_name='Color', to_socket_name='Emission Color')
        if mix_node:
            for input_ in mix_node.inputs:
                if input_.name.startswith('Color') and not input_.is_linked:
                    return input_.default_value
        else:
            return shader.inputs['Emission Color'].default_value

    def get_normal_strength(self, material, shader):
        # Normal Map [Normal] -> [Normal] Principled BSDF
        normal_map = get_from_node(
            material.node_tree, 'NORMAL_MAP', to_node=shader,
            from_socket_name='Normal', to_socket_name='Normal')
        if normal_map:
            return normal_map.inputs['Strength'].default_value
        else:
            return 1

#------------------
class TextureMixin(object):
    def get_diffuse(self, material, shader):
        for i in ('Color', 'Alpha'):
            # Image Texture [Color/Alpha] -> [Socket] Principled BSDF
            node = get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=shader,
                from_socket_name=i, to_socket_name='Base Color')
            if node:
                return node

    def get_normal_map(self, material, shader):
        # Normal Map [Normal] -> [Normal] Principled BSDF
        normal_map = get_from_node(
            material.node_tree, 'NORMAL_MAP', to_node=shader,
            from_socket_name='Normal', to_socket_name='Normal')
        if normal_map:
            # Image Texture [Color] -> [Color] Normal Map
            return get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=normal_map,
                from_socket_name='Color', to_socket_name='Color')

    def get_emission_map(self, material, shader):
        # emission map pipeline
        # Image Texture [Color] -> [Emission Strength] Principled BSDF
        if shader.inputs['Emission Strength'].is_linked:
            node = get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=shader,
                from_socket_name='Color', to_socket_name='Emission Strength')
            if node:
                return node

        # emission color pipeline
        # Mix RGB [Color] -> [Emission] Principled BSDF
        mix_node = get_from_node(
            material.node_tree, 'MIX_RGB', to_node=shader,
            from_socket_name='Color', to_socket_name='Emission Color')
        if mix_node:
            # Image Texture [Color] -> [Color1/Color2] Mix
            for input_ in mix_node.inputs:
                if input_.name.startswith('Color') and input_.is_linked:
                    return get_from_node(
                        material.node_tree, 'TEX_IMAGE', to_node=mix_node,
                        from_socket_name='Color', to_socket_name=input_.name)
        else:
            # Image Texture [Color] -> [Emission] Principled BSDF
            return get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=shader,
                from_socket_name='Color', to_socket_name='Emission Color')

    def get_specular_map(self, material, shader):
        # Math [Value] -> [Specular IOR Level] Principled BSDF
        math_node = get_from_node(
            material.node_tree, 'MATH', to_node=shader,
            from_socket_name='Value', to_socket_name='Specular IOR Level')
        if math_node:
            # Image Texture [Color] -> [Input] Math
            return get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=math_node,
                from_socket_name='Color', to_socket_name='Value')
        else:
            # Image Texture [Color] -> [Specular IOR Level] Principled BSDF
            return get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=shader,
                from_socket_name='Color', to_socket_name='Specular IOR Level')

    def get_roughness_map(self, material, shader):
        # Math [Value] -> [Roughness] Principled BSDF
        math_node = get_from_node(
            material.node_tree, 'MATH', to_node=shader,
            from_socket_name='Value', to_socket_name='Roughness')
        if math_node:
            # Image Texture [Color] -> [Input] Math
            return get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=math_node,
                from_socket_name='Color', to_socket_name='Value')
        else:
            # Image Texture [Color] -> [Roughness] Principled BSDF
            return get_from_node(
                material.node_tree, 'TEX_IMAGE', to_node=shader,
                from_socket_name='Color', to_socket_name='Roughness')

    def get_parallax_map(self, material, shader):
        return

    def make_texture(self, i, image_texture):
        raise NotImplementedError()

    def make_empty_texture(self, i):
        raise NotImplementedError()

    def get_images(self, material, shader):
        return tuple()

    def make_textures(self, material):
        results = []

        shader = None
        if material.node_tree is not None:
            output = get_root_node(material.node_tree, 'OUTPUT_MATERIAL')
            if output:
                shader = get_from_node(
                    material.node_tree, 'BSDF_PRINCIPLED', to_node=output,
                    from_socket_name='BSDF', to_socket_name='Surface')

        if shader:
            image_textures = self.get_images(material, shader)
            last_texid = 0
            for i, (type_, image_texture) in enumerate(reversed(image_textures)):
                if image_texture is not None:
                    last_texid = len(image_textures) - i - 1
                    break

            for i, (type_, image_texture) in enumerate(image_textures):
                if image_texture is None:
                    if self._empty_textures:  # fill empty slot
                        result = self.make_empty_texture(type_)
                        results.append((type_,) + result)
                    elif self._render_type == 'rp':
                        break

                elif image_texture:
                    result = self.make_texture(type_, image_texture)
                    results.append((type_,) + result)

                if i >= last_texid and self._render_type == 'rp':
                    break

        return results

#--------------
class VertexMixin(object):
    def get_sharp_vertices(self, mesh):
        results = []
        #if mesh.use_auto_smooth:
        for edge in mesh.edges:
            if edge.use_edge_sharp:
                for vertex_id in edge.vertices:
                    results.append(vertex_id)

        return results

    def get_tangent_bitangent(self, mesh):
        results = {}

        for uv_name, uv_layer in mesh.uv_layers.items():
            mesh.calc_tangents(uvmap=uv_name)
            results[uv_name] = []
            for i, loop in mesh.loops.items():
                results[uv_name].append((
                    mathutils.Vector(loop.tangent),
                    mathutils.Vector(loop.bitangent),
                    loop.bitangent_sign,
                ))
            mesh.free_tangents()

        return results

    def can_share_vertex(self, mesh, vertex, loop_id, uv, normal):
        if not mesh.uv_layers:
            return True

        if not mesh.uv_layers.active:
            return True

        uv_loop = mesh.uv_layers.active.data[loop_id]
        # if uv_equals(uv_loop.uv.to_2d(), uv) and normal_equals(vertex.normal, normal):
        if uv_equals(uv_loop.uv.to_2d(), uv) and normal_equals(mesh.loops[loop_id].normal, normal):
            return True

        return False

#-----------------------------------------------------------------------
NOT_MERGED_TYPES = (
    'Portal',
    'Text',
    'Sprite',
    'Transparent',
    'Protected',
    'Dynamic',
    'Flipbook',
    'Slider',
    'Alpha',
)


class Exporter(GeomMixin, MaterialMixin, TextureMixin, VertexMixin):
    def __init__(self, args):
        self._inputs = args.inputs
        self._output = args.output

        if self._inputs:
            bpy.ops.wm.open_mainfile(filepath=self._inputs[0])
            for i in self._inputs[1:]:
                bpy.ops.wm.append(filepath=i)

        # export type
        self._export_type = args.export or 'scene'
        self._action = args.action  # animation/action name to export

        # render type
        self._render_type = args.render or 'default'

        # animations
        self._speed_scale = args.speed or 1

        # geom scale
        self._geom_scale = args.scale or 1

        # scripting
        self._script_names = (args.exec or '').split(',')
        self._script_locals = {}

        # merging
        self._merge = args.merge
        self._keep = args.keep

        # materials, textures, UVs
        self._no_materials = args.no_materials is True
        self._no_extra_uv = args.no_extra_uv is True
        self._no_textures = args.no_textures is True
        self._empty_textures = args.empty_textures
        self._set_origin = args.set_origin is True

    def get_cwd(self):
        if self._inputs:
            return os.path.dirname(self._inputs[0])
        else:
            return ''

    def execute_script(self, name):
        script = bpy.data.texts.get(name)
        if script:
            code = compile(script.as_string(), name, 'exec')
            exec(code, None, self._script_locals)

            if 'SPEED_SCALE' in self._script_locals:
                self._speed_scale = self._script_locals['SPEED_SCALE']

    def can_merge(self, obj):
        if not self._merge:
            return False

        collection = get_object_collection(obj)
        if not collection:
            return False

        if is_collision(obj):
            return False

        if not is_object_visible(obj):
            return False

        obj_props = get_object_properties(obj)
        if obj_props.get('type') in NOT_MERGED_TYPES:
            return False

        if obj.type == 'MESH':
            for material in obj.data.materials:
                if material.node_tree:
                    for node in material.node_tree.nodes:
                        if node.type == 'ATTRIBUTE':
                            return False

            return True

        return False

    def make_root_node(self):
        raise NotImplementedError()

    def make_empty(self, parent_node, obj):
        raise NotImplementedError()

    def make_mesh(self, parent_node, obj):
        raise NotImplementedError()

    def make_light(self, parent_node, obj):
        raise NotImplementedError()

    def make_armature(self, parent_node, obj):
        raise NotImplementedError()

    def make_animation(self, parent_node, obj=None):
        for child in bpy.data.objects:
            if not is_object_visible(child):
                continue

            if child.type == 'ARMATURE':
                if self._action:
                    action = bpy.data.actions[self._action]
                    self.make_action(parent_node, child, action)
                else:
                    for action_name, action in bpy.data.actions.items():
                        self.make_action(parent_node, child, action)

    def make_node(self, parent_node, obj=None):
        node = None

        if obj is None:
            node = parent_node

        else:
            if obj.type == 'EMPTY':
                node = self.make_empty(parent_node, obj)

            elif obj.type == 'ARMATURE':
                node = self.make_armature(parent_node, obj)
#                if is_object_visible(obj) :
#                    node = self.make_armature(parent_node, obj)

            elif obj.type == 'MESH':
                node = self.make_mesh(parent_node, obj)

            elif obj.type in ('LIGHT', 'LAMP'):
                if obj.data.type in ('SPOT', 'POINT'):
                    node = self.make_light(parent_node, obj)

        if node is None:
            return

        # make children of the current node
        if obj is None:  # root objects
            children = filter(lambda o: not o.parent, bpy.data.objects)
        else:  # children on current object
            children = obj.children

        for child in children:
            if not is_object_visible(child) and not is_collision(child):
                continue

            if self._export_type == 'collision':
                if child.type in ('ARMATURE', 'LIGHT', 'LAMP'):
                    continue

                if child.type == 'MESH' and not is_collision(child):
                    continue

            self.make_node(node, child)

    def convert(self):
        if self._script_names:
            for script_name in self._script_names:
                if script_name:
                    self.execute_script(script_name)

        if self._merge:
            for collection in bpy.data.collections:
                if collection.name == 'RigidBodyWorld':
                    continue

                objects = list(filter(self.can_merge, collection.objects))
                if not objects:
                    continue

                bpy.ops.object.select_all(action='DESELECT')
                for obj in objects:
                    obj.select_set(state=True)
                set_active_object(objects[0])

                context = {
                    'active_object': objects[0],
                    'selected_objects': objects,
                    'selected_editable_objects': objects,
                }

                bpy.ops.object.join(context)
                bpy.ops.object.select_all(action='DESELECT')
                bpy.context.view_layer.objects.active.name = collection.name
                set_active_object(None)

        self._root = self.make_root_node()

        if self._export_type == 'animation':
            self.make_animation(self._root)
        else:
            self.make_node(self._root)
            if self._export_type == 'all':
                self.make_animation(self._root)

        return self._root