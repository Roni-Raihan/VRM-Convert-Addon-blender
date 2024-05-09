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
import json
import struct

class VRMread():
    def baca(data):
        with open(data, 'rb') as f:
            assert f.read(4) == b'glTF'
            assert struct.unpack('<I', f.read(4))[0] == 2
            full_size = struct.unpack('<I', f.read(4))

            chunk_type = None
            chunk_data = None
            while True:
                chunk_size = struct.unpack('<I', f.read(4))[0]
                chunk_type = f.read(4)
                chunk_data = f.read(chunk_size)
                if chunk_type == b'JSON':
                    break

            if chunk_type == b'JSON':
                gltf_data = json.loads(chunk_data)
                
            f.close()
        if 'VRM' in gltf_data.get('extensions', {}):
            dmta = bpy.context.scene.vrm_meta
            vrm_meta = gltf_data['extensions']['VRM']['meta']
            
            if 'title' in vrm_meta:
                dmta.nama = vrm_meta['title']
                
            if 'version' in vrm_meta:
                dmta.versi_model = vrm_meta['version']
            
            if 'author' in vrm_meta:
                dmta.author = vrm_meta['author']
            
            if 'contactInformation' in vrm_meta:
                dmta.contact = vrm_meta['contactInformation']
            
            if 'reference' in vrm_meta:
                dmta.reference = vrm_meta['reference']
            
            if 'otherPermissionUrl' in vrm_meta:
                dmta.otherPermissionUrl = vrm_meta['otherPermissionUrl']
                
            if 'otherLicenseUrl' in vrm_meta:
                dmta.licenseurl = vrm_meta['otherLicenseUrl']
                
            if 'allowedUserName' in vrm_meta and vrm_meta['allowedUserName'] == 'Everyone':
                dmta.alloweduser = 'Everyone'
            elif 'allowedUserName' in vrm_meta and vrm_meta['allowedUserName'] == 'ExplicitlyLicensedPerson':
                dmta.alloweduser = 'ExplicitlyLicensedPerson'
            else:
                dmta.alloweduser = 'OnlyAuthor'
                
            if 'violentUssageName' in vrm_meta and vrm_meta['violentUssageName'] == 'Allow':
                dmta.violentussage = 'Allow'
            else:
                dmta.violentussage = 'Disallow'
                    
            if 'commercialUssageName' in vrm_meta and vrm_meta['commercialUssageName'] == 'Allow':
                dmta.commercial = 'Allow'
            else:
                dmta.commercial = 'Disallow'
                    
            if 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'Redistribution_Prohibited':
                dmta.license = 'Redistribution_Prohibited'
            elif 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'CC0':
                dmta.license = 'CC0'
            elif 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'CC_BY':
                dmta.license = 'CC_BY'
            elif 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'CC_BY_NC':
                dmta.license = 'CC_BY_NC'
            elif 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'CC_BY_SA':
                dmta.license = 'CC_BY_SA'
            elif 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'CC_BY_ND':
                dmta.license = 'CC_BY_ND'
            elif 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'CC_BY_NC_SA':
                dmta.license = 'CC_BY_NC_SA'
            elif 'licenseName' in vrm_meta and vrm_meta['licenseName'] == 'CC_BY_NC_ND':
                dmta.license = 'CC_BY_NC_ND'
            else:
                dmta.license = 'Other'
        return {'FINISHED'}
