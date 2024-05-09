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
import os
from os.path import dirname, join, basename
from urllib.parse import unquote, quote
from os.path import normpath
from os import sep

from .dasar.g2 import Sampler
from .dasar.g2_constants import TextureFilter, TextureWrap
from .dasar.g2_binary import BinaryData, import_user_extensions
from .dasar.g2b_conversion import texture_transform_gltf_to_blender

#-------------------------------------------------------------
def uri_to_path(uri):
    uri = uri.replace('\\', '/') # Some files come with \\ as dir separator
    uri = unquote(uri)
    return normpath(uri)

# Note that Image is not a glTF2.0 object
class BlenderImage():
    """Manage Image."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def create(gltf, img_idx):
        """Image creation."""
        img = gltf.data.images[img_idx]

        if img.blender_image_name is not None:
            # Image is already used somewhere
            return

        import_user_extensions('gather_import_image_before_hook', gltf, img)

        if img.uri is not None and not img.uri.startswith('data:'):
            blender_image = create_from_file(gltf, img_idx)
        else:
            blender_image = create_from_data(gltf, img_idx)

        if blender_image:
            img.blender_image_name = blender_image.name

        import_user_extensions('gather_import_image_after_hook', gltf, img, blender_image)


def create_from_file(gltf, img_idx):
    # Image stored in a file

    num_images = len(bpy.data.images)

    img = gltf.data.images[img_idx]

    path = join(dirname(gltf.filename), uri_to_path(img.uri))
    path = os.path.abspath(path)
    if bpy.data.is_saved and bpy.context.preferences.filepaths.use_relative_paths:
        try:
            path = bpy.path.relpath(path)
        except:
            # May happen on Windows if on different drives, eg. C:\ and D:\
            pass

    img_name = img.name or basename(path)

    try:
        blender_image = bpy.data.images.load(
            path,
            check_existing=True,
        )

        needs_pack = gltf.import_settings['import_pack_images']
        if needs_pack:
            blender_image.pack()

    except RuntimeError:
        gltf.log.error("Missing image file (index %d): %s" % (img_idx, path))
        blender_image = _placeholder_image(img_name, os.path.abspath(path))

    if len(bpy.data.images) != num_images:  # If created a new image
        blender_image.name = img_name

    return blender_image


def create_from_data(gltf, img_idx):
    # Image stored as data => pack
    img_data = BinaryData.get_image_data(gltf, img_idx)
    if img_data is None:
        return
    img_name = gltf.data.images[img_idx].name or 'Image_%d' % img_idx

    # Create image, width and height are dummy values
    blender_image = bpy.data.images.new(img_name, 8, 8)
    # Set packed file data
    blender_image.pack(data=img_data.tobytes(), data_len=len(img_data))
    blender_image.source = 'FILE'

    return blender_image

def _placeholder_image(name, path):
    image = bpy.data.images.new(name, 128, 128)
    # allow the path to be resolved later
    image.filepath = path
    image.source = 'FILE'
    return image

#---------------------------------------------------------------------
def texture(
    mh,
    tex_info,
    location, # Upper-right corner of the TexImage node
    label, # Label for the TexImg node
    color_socket,
    alpha_socket=None,
    is_data=False,
    forced_image=None
):
    """Creates nodes for a TextureInfo and hooks up the color/alpha outputs."""
    x, y = location
    pytexture = mh.gltf.data.textures[tex_info.index]

    import_user_extensions('gather_import_texture_before_hook', mh.gltf, pytexture, mh, tex_info, location, label, color_socket, alpha_socket, is_data)

    if pytexture.sampler is not None:
        pysampler = mh.gltf.data.samplers[pytexture.sampler]
    else:
        pysampler = Sampler.from_dict({})

    needs_uv_map = False  # whether to create UVMap node

    # Image Texture
    tex_img = mh.node_tree.nodes.new('ShaderNodeTexImage')
    tex_img.location = x - 240, y
    tex_img.label = label

    # Get image
    if forced_image is None:

        if mh.gltf.import_settings['import_webp_texture'] is True:
            # Get the WebP image if there is one
            if pytexture.extensions \
                    and 'EXT_texture_webp' in pytexture.extensions \
                    and pytexture.extensions['EXT_texture_webp']['source'] is not None:
                source = pytexture.extensions['EXT_texture_webp']['source']
            elif pytexture.source is not None:
                source = pytexture.source
        else:
            source = pytexture.source

        if mh.gltf.import_settings['import_webp_texture'] is False and source is None:
            # In case webp is not used as a fallback, use this as main texture
            if pytexture.extensions \
                    and 'EXT_texture_webp' in pytexture.extensions \
                    and pytexture.extensions['EXT_texture_webp']['source'] is not None:
                source = pytexture.extensions['EXT_texture_webp']['source']

        if source is not None:
            BlenderImage.create(mh.gltf, source)
            pyimg = mh.gltf.data.images[source]
            blender_image_name = pyimg.blender_image_name
            if blender_image_name:
                tex_img.image = bpy.data.images[blender_image_name]
    else:
        tex_img.image = forced_image
    # Set colorspace for data images
    if is_data:
        if tex_img.image:
            tex_img.image.colorspace_settings.is_data = True
    # Set filtering
    set_filtering(tex_img, pysampler)
    # Outputs
    if color_socket is not None:
        mh.node_tree.links.new(color_socket, tex_img.outputs['Color'])
    if alpha_socket is not None:
        mh.node_tree.links.new(alpha_socket, tex_img.outputs['Alpha'])
    # Inputs
    uv_socket = tex_img.inputs[0]

    x -= 340

    # Do wrapping
    wrap_s = pysampler.wrap_s
    wrap_t = pysampler.wrap_t
    if wrap_s is None:
        wrap_s = TextureWrap.Repeat
    if wrap_t is None:
        wrap_t = TextureWrap.Repeat
    # If wrapping is the same in both directions, just set tex_img.extension
    if wrap_s == wrap_t == TextureWrap.Repeat:
        tex_img.extension = 'REPEAT'
    elif wrap_s == wrap_t == TextureWrap.ClampToEdge:
        tex_img.extension = 'EXTEND'
    elif wrap_s == wrap_t == TextureWrap.MirroredRepeat:
        tex_img.extension = 'MIRROR'
    else:
        # Otherwise separate the UV components and use math nodes to compute
        # the wrapped UV coordinates
        # => [Separate XYZ] => [Wrap for S] => [Combine XYZ] =>
        #                   => [Wrap for T] =>

        tex_img.extension = 'EXTEND'  # slightly better errors near the edge than REPEAT

        # Combine XYZ
        com_uv = mh.node_tree.nodes.new('ShaderNodeCombineXYZ')
        com_uv.location = x - 140, y - 100
        mh.node_tree.links.new(uv_socket, com_uv.outputs[0])
        u_socket = com_uv.inputs[0]
        v_socket = com_uv.inputs[1]
        x -= 200

        for i in [0, 1]:
            wrap = [wrap_s, wrap_t][i]
            socket = [u_socket, v_socket][i]
            if wrap == TextureWrap.Repeat:
                # WRAP node for REPEAT
                math = mh.node_tree.nodes.new('ShaderNodeMath')
                math.location = x - 140, y + 30 - i*200
                math.operation = 'WRAP'
                math.inputs[1].default_value = 0
                math.inputs[2].default_value = 1
                mh.node_tree.links.new(socket, math.outputs[0])
                socket = math.inputs[0]
            elif wrap == TextureWrap.MirroredRepeat:
                # PINGPONG node for MIRRORED_REPEAT
                math = mh.node_tree.nodes.new('ShaderNodeMath')
                math.location = x - 140, y + 30 - i*200
                math.operation = 'PINGPONG'
                math.inputs[1].default_value = 1
                mh.node_tree.links.new(socket, math.outputs[0])
                socket = math.inputs[0]
            else:
                # Pass-through CLAMP since the tex_img node is set to EXTEND
                pass
            if i == 0:
                u_socket = socket
            else:
                v_socket = socket
        x -= 200

        # Separate XYZ
        sep_uv = mh.node_tree.nodes.new('ShaderNodeSeparateXYZ')
        sep_uv.location = x - 140, y - 100
        mh.node_tree.links.new(u_socket, sep_uv.outputs[0])
        mh.node_tree.links.new(v_socket, sep_uv.outputs[1])
        uv_socket = sep_uv.inputs[0]
        x -= 200

        needs_uv_map = True

    # UV Transform (for KHR_texture_transform)
    needs_tex_transform = 'KHR_texture_transform' in (tex_info.extensions or {})
    if needs_tex_transform:
        mapping = mh.node_tree.nodes.new('ShaderNodeMapping')
        mapping.location = x - 160, y + 30
        mapping.vector_type = 'POINT'
        # Outputs
        mh.node_tree.links.new(uv_socket, mapping.outputs[0])
        # Inputs
        uv_socket = mapping.inputs[0]

        transform = tex_info.extensions['KHR_texture_transform']
        transform = texture_transform_gltf_to_blender(transform)
        mapping.inputs['Location'].default_value[0] = transform['offset'][0]
        mapping.inputs['Location'].default_value[1] = transform['offset'][1]
        mapping.inputs['Rotation'].default_value[2] = transform['rotation']
        mapping.inputs['Scale'].default_value[0] = transform['scale'][0]
        mapping.inputs['Scale'].default_value[1] = transform['scale'][1]

        x -= 260
        needs_uv_map = True

    # UV Map
    uv_idx = tex_info.tex_coord or 0
    try:
        uv_idx = tex_info.extensions['KHR_texture_transform']['texCoord']
    except Exception:
        pass
    if uv_idx != 0 or needs_uv_map:
        uv_map = mh.node_tree.nodes.new('ShaderNodeUVMap')
        uv_map.location = x - 160, y - 70
        uv_map.uv_map = 'UVMap' if uv_idx == 0 else 'UVMap.%03d' % uv_idx
        # Outputs
        mh.node_tree.links.new(uv_socket, uv_map.outputs[0])

    import_user_extensions('gather_import_texture_after_hook', mh.gltf, pytexture, mh.node_tree, mh, tex_info, location, label, color_socket, alpha_socket, is_data)

def set_filtering(tex_img, pysampler):
    """Set the filtering/interpolation on an Image Texture from the glTf sampler."""
    minf = pysampler.min_filter
    magf = pysampler.mag_filter

    # Ignore mipmapping
    if minf in [TextureFilter.NearestMipmapNearest, TextureFilter.NearestMipmapLinear]:
        minf = TextureFilter.Nearest
    elif minf in [TextureFilter.LinearMipmapNearest, TextureFilter.LinearMipmapLinear]:
        minf = TextureFilter.Linear

    # If both are nearest or the only specified one was nearest, use nearest.
    if (minf, magf) in [
        (TextureFilter.Nearest, TextureFilter.Nearest),
        (TextureFilter.Nearest, None),
        (None, TextureFilter.Nearest),
    ]:
        tex_img.interpolation = 'Closest'
    else:
        tex_img.interpolation = 'Linear'
