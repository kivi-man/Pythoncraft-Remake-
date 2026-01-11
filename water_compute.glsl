#version 430

layout(local_size_x = 8, local_size_y = 8, local_size_z = 8) in;

// 3D texture for water levels (0-7, 255=no water)
layout(binding = 0, r8ui) uniform uimage3D water_data;

// 3D texture for block types (0=air, 1=solid, 8=water)
layout(binding = 1, r8ui) uniform uimage3D block_data;

// Output for next frame
layout(binding = 2, r8ui) uniform uimage3D water_output;

uniform ivec3 world_size;

void main() {
    ivec3 pos = ivec3(gl_GlobalInvocationID.xyz);
    
    // Bounds check
    if (any(greaterThanEqual(pos, world_size))) {
        return;
    }
    
    uint current_level = imageLoad(water_data, pos).r;
    uint block_type = imageLoad(block_data, pos).r;
    
    // If no water here, skip
    if (current_level == 255u) {
        imageStore(water_output, pos, uvec4(255u));
        return;
    }
    
    // If not water block, remove water data
    if (block_type != 8u) {
        imageStore(water_output, pos, uvec4(255u));
        return;
    }
    
    // 1️⃣ AŞAĞI AKIŞ
    ivec3 below = pos + ivec3(0, -1, 0);
    if (below.y >= 0) {
        uint below_block = imageLoad(block_data, below).r;
        uint below_water = imageLoad(water_data, below).r;
        
        // Eğer aşağı hava ise, oraya su akıt (kaynak seviyesi)
        if (below_block == 0u) {
            imageStore(water_output, below, uvec4(0u));
            imageStore(water_output, pos, uvec4(current_level));
            return;
        }
        
        // Eğer aşağı su ise ve zayıfsa, güçlendir
        if (below_block == 8u && below_water > 0u) {
            imageStore(water_output, below, uvec4(0u));
            imageStore(water_output, pos, uvec4(current_level));
            return;
        }
    }
    
    // 2️⃣ YATAY YAYILMA
    if (current_level < 7u) {
        ivec3 neighbors[4] = ivec3[](
            pos + ivec3(1, 0, 0),
            pos + ivec3(-1, 0, 0),
            pos + ivec3(0, 0, 1),
            pos + ivec3(0, 0, -1)
        );
        
        uint next_level = current_level + 1u;
        
        for (int i = 0; i < 4; i++) {
            ivec3 n = neighbors[i];
            
            // Bounds check
            if (any(lessThan(n, ivec3(0))) || any(greaterThanEqual(n, world_size))) {
                continue;
            }
            
            uint n_block = imageLoad(block_data, n).r;
            uint n_water = imageLoad(water_data, n).r;
            
            // Hava ise, su yayıl
            if (n_block == 0u) {
                imageStore(water_output, n, uvec4(next_level));
            }
            // Su ise ve daha zayıfsa, güçlendir
            else if (n_block == 8u && n_water > next_level) {
                imageStore(water_output, n, uvec4(next_level));
            }
        }
    }
    
    // Mevcut seviyeyi koru
    imageStore(water_output, pos, uvec4(current_level));
}
