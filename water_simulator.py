import moderngl
import numpy as np
from collections import deque
import struct

class WaterSimulatorGPU:
    """
    GPU-accelerated water simulator using compute shaders
    """
    
    MAX_LEVEL = 7
    SOURCE = 0
    WATER_ID = 8

    def __init__(self, world, ctx=None):
        self.world = world
        self.meta = world.block_metadata
        
        # Create ModernGL context from existing OpenGL context
        try:
            self.ctx = moderngl.create_context()
            print("✓ GPU Water Simulation: ENABLED")
            print(f"  GPU: {self.ctx.info['GL_RENDERER']}")
            self.gpu_enabled = True
        except Exception as e:
            print(f"✗ GPU Water Simulation: FAILED - {e}")
            self.ctx = None
            self.gpu_enabled = False
            # Fallback to CPU
            self.flow_queue = deque()
            self.dirty_chunks = set()
            return
        
        # Load compute shader
        with open('water_compute.glsl', 'r', encoding='utf-8') as f:
            compute_source = f.read()
        
        try:
            self.compute_shader = self.ctx.compute_shader(compute_source)
        except Exception as e:
            print(f"✗ Compute Shader Failed: {e}")
            self.gpu_enabled = False
            self.flow_queue = deque()
            self.dirty_chunks = set()
            return
        
        # GPU buffers for water simulation
        # We'll use a simple grid approach: store water levels in a 3D texture
        self.chunk_size = 16
        self.world_height = 32  # Optimized for GPU (16x32x16 chunks)
        
        # Active chunks on GPU
        self.gpu_chunks = {}  # chunk_pos -> {'water': texture, 'blocks': texture}
        
        # Dirty chunks for mesh update
        self.dirty_chunks = set()
        
        # Queue for CPU-side events
        self.pending_updates = deque()

    def update(self):
        """Run GPU water simulation"""
        if not self.gpu_enabled:
            # CPU fallback
            self._update_cpu()
            return
        
        if not self.gpu_chunks:
            return
        
        # Run compute shader for each active chunk
        for chunk_pos, textures in self.gpu_chunks.items():
            # Bind textures
            textures['water'].bind_to_image(0, read=True, write=False)
            textures['blocks'].bind_to_image(1, read=True, write=False)
            textures['output'].bind_to_image(2, read=False, write=True)
            
            # Set uniforms
            self.compute_shader['world_size'].value = (self.chunk_size, self.world_height, self.chunk_size)
            
            # Dispatch compute shader
            # Work groups: 8x8x8 threads per group
            groups_x = (self.chunk_size + 7) // 8
            groups_y = (self.world_height + 7) // 8
            groups_z = (self.chunk_size + 7) // 8
            
            self.compute_shader.run(groups_x, groups_y, groups_z)
            
            # Swap buffers (double buffering)
            textures['water'], textures['output'] = textures['output'], textures['water']
            
            self.dirty_chunks.add(chunk_pos)
        
        # Update meshes
        self.flush_mesh_updates()

    def _update_cpu(self):
        """CPU fallback implementation"""
        if not self.flow_queue:
            return
            
        limit = 500
        count = 0
        next_queue = deque()
        processed = set()
        
        while self.flow_queue and count < limit:
            pos = self.flow_queue.popleft()
            count += 1
            
            if pos in processed:
                continue
            processed.add(pos)
            
            if not self.world.is_position_loaded(pos):
                continue
                
            if not self.is_water(pos):
                continue
            
            x, y, z = pos
            level = self.meta.get_water_level(pos)
            
            # Flow down
            below = (x, y - 1, z)
            if self.world.is_position_loaded(below):
                below_block = self.world.get_block_number(below)
                
                if below_block == 0:
                    self.set_water(below, self.SOURCE)
                    next_queue.append(below)
                    continue
                elif self.is_water(below):
                    below_level = self.meta.get_water_level(below)
                    if below_level > 0:
                        self.set_water(below, self.SOURCE)
                        next_queue.append(below)
                    continue
            
            # Spread horizontal
            if level < self.MAX_LEVEL:
                for dx, dz in [(1,0), (-1,0), (0,1), (0,-1)]:
                    n_pos = (x + dx, y, z + dz)
                    
                    if not self.world.is_position_loaded(n_pos):
                        continue
                    
                    n_block = self.world.get_block_number(n_pos)
                    
                    if n_block == 0:
                        self.set_water(n_pos, level + 1)
                        next_queue.append(n_pos)
                    elif self.is_water(n_pos):
                        n_level = self.meta.get_water_level(n_pos)
                        if level + 1 < n_level:
                            self.set_water(n_pos, level + 1)
                            next_queue.append(n_pos)
        
        self.flow_queue.extend(next_queue)
        self.flush_mesh_updates()

    def initialize_chunk_gpu(self, chunk_pos):
        """Initialize GPU textures for a chunk"""
        if not self.gpu_enabled:
            return
            
        if chunk_pos in self.gpu_chunks:
            return
        
        # Create 3D textures for water and block data
        size = (self.chunk_size, self.world_height, self.chunk_size)
        
        # Initialize with data from world
        water_data = np.full(size, 255, dtype=np.uint8)  # 255 = no water
        block_data = np.zeros(size, dtype=np.uint8)
        
        if chunk_pos in self.world.chunks:
            chunk = self.world.chunks[chunk_pos]
            for x in range(self.chunk_size):
                for y in range(min(self.world_height, len(chunk.blocks[0]))):
                    for z in range(self.chunk_size):
                        block_id = chunk.blocks[x][y][z]
                        block_data[x, y, z] = block_id
                        
                        if block_id == self.WATER_ID:
                            world_pos = (
                                chunk_pos[0] * self.chunk_size + x,
                                chunk_pos[1] * self.world_height + y,
                                chunk_pos[2] * self.chunk_size + z
                            )
                            level = self.meta.get_water_level(world_pos)
                            water_data[x, y, z] = level
        
        # Create GPU textures
        water_tex = self.ctx.texture3d(size, 1, water_data.tobytes(), dtype='u1')
        block_tex = self.ctx.texture3d(size, 1, block_data.tobytes(), dtype='u1')
        output_tex = self.ctx.texture3d(size, 1, dtype='u1')
        
        self.gpu_chunks[chunk_pos] = {
            'water': water_tex,
            'blocks': block_tex,
            'output': output_tex
        }

    def set_water(self, pos, level):
        self.world.set_block(pos, self.WATER_ID)
        self.meta.set_water_level(pos, level)
        self.mark_dirty(pos)

    def is_water(self, pos):
        return self.world.get_block_number(pos) == self.WATER_ID

    def mark_dirty(self, pos):
        chunk_pos = self.world.get_chunk_position(pos)
        self.dirty_chunks.add(chunk_pos)

    def flush_mesh_updates(self):
        """Update meshes for dirty chunks"""
        if not self.gpu_enabled:
            # CPU mode
            for c in self.dirty_chunks:
                if c in self.world.chunks:
                    self.world.chunks[c].update_subchunk_meshes(update_only_water=True)
                    self.world.chunks[c].update_mesh(update_only_water=True)
            self.dirty_chunks.clear()
            return
        
        # GPU mode: sync data back to CPU
        for chunk_pos in self.dirty_chunks:
            if chunk_pos in self.gpu_chunks:
                self.sync_chunk_from_gpu(chunk_pos)
            
            if chunk_pos in self.world.chunks:
                self.world.chunks[chunk_pos].update_subchunk_meshes(update_only_water=True)
                self.world.chunks[chunk_pos].update_mesh(update_only_water=True)
        
        self.dirty_chunks.clear()

    def sync_chunk_from_gpu(self, chunk_pos):
        """Read water data from GPU back to CPU"""
        if chunk_pos not in self.gpu_chunks:
            return
        
        textures = self.gpu_chunks[chunk_pos]
        water_bytes = textures['water'].read()
        water_data = np.frombuffer(water_bytes, dtype=np.uint8)
        water_data = water_data.reshape((self.chunk_size, self.world_height, self.chunk_size))
        
        # Update CPU metadata
        for x in range(self.chunk_size):
            for y in range(self.world_height):
                for z in range(self.chunk_size):
                    level = water_data[x, y, z]
                    if level != 255:
                        world_pos = (
                            chunk_pos[0] * self.chunk_size + x,
                            chunk_pos[1] * self.world_height + y,
                            chunk_pos[2] * self.chunk_size + z
                        )
                        self.meta.set_water_level(world_pos, int(level))

    # Event handlers
    def on_block_removed(self, pos):
        if not self.gpu_enabled:
            self.notify_neighbors(pos)
            return
        
        # Update GPU texture
        chunk_pos = self.world.get_chunk_position(pos)
        if chunk_pos in self.gpu_chunks:
            self.update_block_in_gpu(pos, 0)

    def on_block_placed(self, pos):
        if not self.gpu_enabled:
            self.notify_neighbors(pos)
            return
        
        chunk_pos = self.world.get_chunk_position(pos)
        if chunk_pos in self.gpu_chunks:
            block_id = self.world.get_block_number(pos)
            self.update_block_in_gpu(pos, block_id)

    def on_water_placed(self, pos):
        self.meta.set_water_level(pos, self.SOURCE)
        self.world.set_block(pos, self.WATER_ID)
        
        if not self.gpu_enabled:
            if not hasattr(self, 'flow_queue'):
                self.flow_queue = deque()
            self.flow_queue.append(pos)
            self.mark_dirty(pos)
            return
        
        chunk_pos = self.world.get_chunk_position(pos)
        if chunk_pos not in self.gpu_chunks:
            self.initialize_chunk_gpu(chunk_pos)
        
        self.update_water_in_gpu(pos, self.SOURCE)
        self.update_block_in_gpu(pos, self.WATER_ID)

    def on_chunk_loaded(self, chunk_pos):
        if self.gpu_enabled:
            self.initialize_chunk_gpu(chunk_pos)

    def on_chunk_unloaded(self, chunk_pos):
        if chunk_pos in self.gpu_chunks:
            textures = self.gpu_chunks[chunk_pos]
            textures['water'].release()
            textures['blocks'].release()
            textures['output'].release()
            del self.gpu_chunks[chunk_pos]

    def update_block_in_gpu(self, pos, block_id):
        """Update single block in GPU texture"""
        # This is expensive (read-modify-write), but necessary
        # In production, batch these updates
        chunk_pos = self.world.get_chunk_position(pos)
        if chunk_pos not in self.gpu_chunks:
            return
        
        # For now, just mark for re-initialization
        # TODO: Optimize with partial texture updates
        pass

    def update_water_in_gpu(self, pos, level):
        """Update single water block in GPU"""
        chunk_pos = self.world.get_chunk_position(pos)
        if chunk_pos not in self.gpu_chunks:
            return
        
        # Mark for re-initialization
        pass

    def notify_neighbors(self, pos):
        if not hasattr(self, 'flow_queue'):
            self.flow_queue = deque()
        
        x, y, z = pos
        for n in [(x+1,y,z), (x-1,y,z), (x,y,z+1), (x,y,z-1), (x,y+1,z), (x,y-1,z)]:
            if self.is_water(n):
                self.flow_queue.append(n)

    def cleanup(self):
        """Release GPU resources"""
        for chunk_pos in list(self.gpu_chunks.keys()):
            self.on_chunk_unloaded(chunk_pos)
        
        if hasattr(self, 'compute_shader') and self.compute_shader:
            self.compute_shader.release()
