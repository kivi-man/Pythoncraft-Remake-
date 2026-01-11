import random
from noise import pnoise2, pnoise3
import math

class TerrainGenerator:
    """
    Generates Minecraft-like terrain using a Biome-based noise system.
    """
    
    def __init__(self, seed=None):
        if seed is None:
            seed = random.randint(0, 10000)
        
        self.seed = seed
        
        # Global Settings
        self.sea_level = 65
        self.min_height = 60    # Deepest valley
        self.max_height_gen = 120 # Highest peak limit (soft)
        
        # Noise Settings
        # 1. Biome Selector (Large scale)
        self.biome_scale = 300.0
        
        # 2. Base Detail
        self.detail_scale = 40.0
        
        # 3. Cave Settings
        self.cave_scale = 20.0
        self.cave_threshold = 0.12 # Lower = MORE caves
        
        # Block Mapping
        self.block_map = {
            'air': 0, 'stone': 1, 'grass': 2, 'dirt': 3,
            'bedrock': 7, 'water': 8, 'sand': 12,
            'oak': 17, 'oak_leaves': 18,
            'gold_ore': 14, 'iron_ore': 15, 'coal_ore': 16,
            'diamond_ore': 56, 'redstone_ore': 73
        }
    
    def get_block_number(self, block_name):
        return self.block_map.get(block_name, 0)
        
    def generate_caves(self, blocks, chunk_pos, start_y, chunk_width, chunk_height, chunk_length):
        stone_id = self.get_block_number('stone')
        dirt_id = self.get_block_number('dirt')
        grass_id = self.get_block_number('grass')
        
        for lx in range(chunk_width):
            wx = chunk_pos[0] * chunk_width + lx
            for lz in range(chunk_length):
                wz = chunk_pos[2] * chunk_length + lz
                
                # Get surface height to prevent caves from breaching surface too much
                h = self.get_height(wx, wz)
                
                for ly in range(chunk_height):
                    wy = start_y + ly
                    
                    # Don't carve through bedrock or too high up
                    if wy < 5 or wy > h - 4:
                        continue
                        
                    # 3D Noise for caves
                    noise_val = pnoise3(
                        (wx + self.seed) / self.cave_scale,
                        (wy + self.seed) / self.cave_scale,
                        (wz + self.seed) / self.cave_scale,
                        octaves=4
                    )
                    
                    if noise_val > self.cave_threshold:
                        if blocks[lx][ly][lz] in [stone_id, dirt_id, grass_id]:
                            blocks[lx][ly][lz] = 0 # Air

    def generate_ores(self, blocks, chunk_pos, start_y, chunk_width, chunk_height, chunk_length):
        # Ore configuration: (name, clusters_per_chunk, vein_size, max_global_y)
        ore_configs = [
            ('coal_ore', 15, 6, 128),     # Common, large veins
            ('iron_ore', 12, 4, 64),      # Common, medium veins
            ('redstone_ore', 6, 4, 32),   # Rare, deeper
            ('gold_ore', 4, 3, 28),       # Rare, deeper
            ('diamond_ore', 2, 3, 16),    # Very rare, very deep
        ]
        
        stone_id = self.get_block_number('stone')
        
        for ore_name, clusters, size, max_y in ore_configs:
            ore_id = self.get_block_number(ore_name)
            
            for _ in range(clusters):
                # Pick random spot in chunk
                lx = random.randint(0, chunk_width - 1)
                lz = random.randint(0, chunk_length - 1)
                ly = random.randint(0, chunk_height - 1)
                
                wy = start_y + ly
                if wy > max_y:
                    continue
                
                # Only spawn if we hit stone
                if blocks[lx][ly][lz] == stone_id:
                    # Spawn a cluster/vein
                    vein_count = random.randint(1, size)
                    for _ in range(vein_count):
                        # Move slightly for vein clustering
                        lx = max(0, min(chunk_width - 1, lx + random.randint(-1, 1)))
                        ly = max(0, min(chunk_height - 1, ly + random.randint(-1, 1)))
                        lz = max(0, min(chunk_length - 1, lz + random.randint(-1, 1)))
                        
                        if blocks[lx][ly][lz] == stone_id:
                            blocks[lx][ly][lz] = ore_id

    def get_height(self, world_x, world_z):
        """
        Calculates terrain height using a biome system: Plains, Hills, Mountains.
        """
        # --- 1. BIOME SELECTION ---
        # Large smooth noise to decide nature of terrain
        biome_val = pnoise2(
            (world_x + self.seed) / self.biome_scale, 
            (world_z + self.seed) / self.biome_scale, 
            octaves=2
        )
        # normalize roughly to 0..1
        biome_val = (biome_val + 0.7) * 0.7 
        biome_val = max(0.0, min(1.0, biome_val))
        
        # --- 2. BASE NOISE (The actual shape) ---
        base_noise = pnoise2(
            (world_x + self.seed) / self.detail_scale, 
            (world_z + self.seed) / self.detail_scale, 
            octaves=4,
            persistence=0.5,
            lacunarity=2.0
        )
        
        # --- 3. APPLY BIOME MODIFIERS ---
        
        final_height = self.min_height
        
        if biome_val < 0.4:
            # === PLAINS ===
            # Very flat, slight undulation
            # Amplitude approx 4-8 blocks
            amp = 5.0
            bias = 0.0
            # Flatten the noise (power function preserves sign but squashes values < 1)
            # Actually standard perlin is -1 to 1.
            flat_noise = base_noise * 0.5
            final_height += 5 + (flat_noise * amp)
            
        elif biome_val < 0.7:
            # === HILLS ===
            # Rolling terrain, transitional
            # Amplitude approx 15-20 blocks
            amp = 18.0
            # Interpolate from plains settings based on how far into 'hills' we are could be fancy,
            # but simple switch is safer for distinct look.
            final_height += 10 + (base_noise * amp)
            
        else:
            # === MOUNTAINS ===
            # High amplitude, sharper
            # Nonlinearity: make peaks sharper
            amp = 35.0
            # Sharpness: abs() creates ridges, or pow() creates steepness
            # Let's use a bit of ridged noise behavior: 2 * |0.5 - noise|
            # But simple boosted noise is often closer to Alpha style
            sharp_noise = base_noise
            if sharp_noise > 0:
                sharp_noise = math.pow(sharp_noise, 1.2) # Sharpen peaks
            
            final_height += 15 + (sharp_noise * amp)
            
        # Add a tiny micro-noise layer for surface variation everywhere?
        # Maybe skip for performance/clean look.
        
        return int(final_height)

    def generate_tree(self, blocks, x, y, z, chunk_width, chunk_height, chunk_length,
                     min_height=4, max_height=7, leaf_radius=2):
        height = random.randint(min_height, max_height)
        
        # Trunk
        for i in range(height):
            if y + i < chunk_height:
                blocks[x][y + i][z] = self.get_block_number('oak')
        
        # Leaves
        top_y = y + height
        for dy in range(-leaf_radius, leaf_radius + 1):
            for dx in range(-leaf_radius, leaf_radius + 1):
                for dz in range(-leaf_radius, leaf_radius + 1):
                    # Cheaper distance check (Manhattanish or squared)
                    if dx*dx + dy*dy + dz*dz <= leaf_radius*leaf_radius + 1:
                        if random.random() < 0.7: # Random leaf density
                            bx, by, bz = x + dx, top_y + dy, z + dz
                            if (0 <= bx < chunk_width and 
                                0 <= by < chunk_height and 
                                0 <= bz < chunk_length):
                                if blocks[bx][by][bz] == 0:
                                    blocks[bx][by][bz] = self.get_block_number('oak_leaves')

    def generate_chunk_blocks(self, chunk_position, chunk_width=16, chunk_height=16, chunk_length=16):
        cx, cy, cz = chunk_position
        
        blocks = [[[0] * chunk_length for _ in range(chunk_height)] for _ in range(chunk_width)]
        
        start_x = cx * chunk_width
        start_y = cy * chunk_height
        start_z = cz * chunk_length
        
        tree_candidates = []
        has_any_block = False
        
        for lx in range(chunk_width):
            for lz in range(chunk_length):
                wx = start_x + lx
                wz = start_z + lz
                
                h = self.get_height(wx, wz)
                # Terrain depth: 80 blocks below the surface
                h_min = h - 80
                bedrock_y = h - 81
                
                # Biome check for surface block
                surface = 'grass'
                if h < self.sea_level + 2:
                    surface = 'sand'
                
                # Fill vertical slice for this chunk
                for ly in range(chunk_height):
                    wy = start_y + ly
                    
                    if h_min <= wy < h:
                        if wy < h - 3: b = 'stone'
                        elif wy < h - 1: b = 'dirt'
                        else: b = surface
                        blocks[lx][ly][lz] = self.get_block_number(b)
                        has_any_block = True
                        
                    elif wy == bedrock_y:
                        blocks[lx][ly][lz] = self.get_block_number('bedrock')
                        has_any_block = True
                    
                    # Water
                    elif h <= wy <= self.sea_level:
                        blocks[lx][ly][lz] = self.get_block_number('water')
                        has_any_block = True
                        
                # Tree Logic
                if surface == 'grass' and h > self.sea_level:
                    if start_y <= h < start_y + chunk_height:
                        if random.random() < 0.01:
                            tree_candidates.append((lx, h - start_y, lz))

        if not has_any_block and not tree_candidates:
            return blocks 

        # CAVE GENERATION
        self.generate_caves(blocks, chunk_position, start_y, chunk_width, chunk_height, chunk_length)

        # ORE GENERATION
        self.generate_ores(blocks, chunk_position, start_y, chunk_width, chunk_height, chunk_length)

        for tx, ty, tz in tree_candidates:
            self.generate_tree(blocks, tx, ty, tz, chunk_width, chunk_height, chunk_length)
            
        return blocks

if __name__ == "__main__":
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        
        gen = TerrainGenerator(seed=random.randint(0, 9999))
        print(f"Seed: {gen.seed}")
        
        W, D = 200, 200
        hmap = np.zeros((D, W))
        
        for z in range(D):
            for x in range(W):
                hmap[z, x] = gen.get_height(x, z)
                
        plt.figure(figsize=(10, 8))
        plt.imshow(hmap, cmap='terrain', origin='lower')
        plt.colorbar()
        plt.contour(hmap, levels=[gen.sea_level], colors='blue')
        plt.title(f"Biome Terrain (Seed {gen.seed})")
        plt.show()
        
    except ImportError:
        print("Install matplotlib to see visualizer")
