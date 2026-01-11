import math
import time
import random
from collections import deque

import save
import chunk
import settings

import block_type
import texture_manager
import block_metadata
import water_simulator
import light_solver

# import custom block models

import models
import frustum


class World:
	def __init__(self):
		self.settings = settings.Settings()
		self.texture_manager = texture_manager.Texture_manager(16, 16, 256)
		self.block_types = [None]
		
		# Frustum Culling
		self.frustum = frustum.Frustum()
		self.last_chunk_pos = None
		self.target_load_set = set()

		self.block_types = [None]
		
		# Load destroy stage textures
		self.destroy_textures = []
		for i in range(10):
			self.texture_manager.add_texture(f"destroy_stage_{i}")
			self.destroy_textures.append(self.texture_manager.textures.index(f"destroy_stage_{i}"))

		# parse block type data file

		blocks_data_file = open("data/blocks.mcpy")
		blocks_data = blocks_data_file.readlines()
		blocks_data_file.close()

		for block in blocks_data:
			if block[0] in ["\n", "#"]:  # skip if empty line or comment
				continue

			number, props = block.split(":", 1)
			number = int(number)

			# default block

			name = "Unknown"
			model = models.cube
			texture = {"all": "unknown"}
			hardness = 0.0 # Default hardness
			sound = "stone" # Default sound
			is_sprite = False
			sprite_path = None
			light_level = 0

			# read properties

			for prop in props.split(","):
				prop = prop.strip()
				prop = list(filter(None, prop.split(" ", 1)))

				if prop[0] == "sameas":
					sameas_number = int(prop[1])

					name = self.block_types[sameas_number].name
					texture = dict(self.block_types[sameas_number].block_face_textures)
					model = self.block_types[sameas_number].model
					hardness = self.block_types[sameas_number].hardness
					sound = self.block_types[sameas_number].sound
					is_sprite = self.block_types[sameas_number].is_sprite
					sprite_path = self.block_types[sameas_number].sprite_path
					light_level = self.block_types[sameas_number].light_level

				elif prop[0] == "name":
					name = eval(prop[1])
				
				elif prop[0] == "hardness":
					hardness = float(prop[1])

				elif prop[0] == "sprite":
					is_sprite = True
					sprite_path = eval(prop[1])

				elif prop[0][:7] == "texture":
					_, side = prop[0].split(".")
					texture[side] = prop[1].strip()

				elif prop[0] == "model":
					model = eval(prop[1])
				
				elif prop[0] == "light":
					light_level = int(prop[1])

			# Determine sound based on name if not already set (by sameas)
			if sound == "stone":
				sound = "stone" # default
				lower_name = name.lower()
				
				# User specific requests:
				# Sand -> sand
				# Toprak (Dirt/Soil/Grass) -> gravel
				# Oak/Wood/Log -> wood
				# Stone -> stone
				
				if any(s in lower_name for s in ["dirt", "soil", "grass", "gravel"]):
					sound = "gravel"
				elif "sand" in lower_name:
					sound = "sand"
				elif any(s in lower_name for s in ["wood", "planks", "log", "oak", "chest", "crafting table", "sign", "door", "ladder"]):
					if "cobblestone" not in lower_name and "stone" not in lower_name:
						sound = "wood"
				elif any(s in lower_name for s in ["leaves", "sapling", "flower", "mushroom", "sugar cane", "cactus"]):
					sound = "grass"
				elif "snow" in lower_name or "ice" in lower_name:
					sound = "snow"
				elif "cloth" in lower_name or "wool" in lower_name:
					sound = "cloth"
				elif "coral" in lower_name:
					sound = "coral"
				elif "stone" in lower_name or "cobblestone" in lower_name or "ore" in lower_name or "brick" in lower_name:
					sound = "stone"

			# add block type

			_block_type = block_type.Block_type(self.texture_manager, name, texture, model, hardness, sound, is_sprite, sprite_path, light_level)

			if is_sprite and sprite_path:
				# Convert "textures/item/stick.png" to "item/stick"
				tex_name = sprite_path.replace("textures/", "").replace(".png", "")
				self.texture_manager.add_texture(tex_name)
				_block_type.sprite_index = self.texture_manager.textures.index(tex_name)

			while number >= len(self.block_types):
				self.block_types.append(None)
			self.block_types[number] = _block_type

		self.texture_manager.generate_mipmaps()

		# load the world

		self.save = save.Save(self)
		
		# Initialize water simulation system (metadata only, GPU init later)
		self.block_metadata = block_metadata.BlockMetadata()
		self.water_simulator = None  # Will be initialized after OpenGL context is ready

		self.chunks = {}
		self.save.load()
		
		# Mesh update queue system
		self.mesh_update_queue = deque()
		self.mesh_update_set = set() # For fast lookup to avoid duplicates
		
		# Mob persistence (cx, cy, cz) -> list of mob data
		self.persistent_mobs = self.save.load_mobs()
		

		# Initialize Light Solver
		self.light_solver = light_solver.LightSolver(self)
		
		# Mob Spawning
		self.spawn_queue = deque()
		import mob # Lazy import to avoid circular dependency if mob imports world? mob imports entity imports world?
		# actually mob imports entity. entity imports... nothing.
		# mob imports world? no.
		# But pig will need to be imported in main.
		
	def spawn_pigs_in_chunk(self, chunk_position):
		# 10% chance to spawn a colony
		if random.random() < 0.1:
			cx, cy, cz = chunk_position
			
			# Determine how many pigs (3 to 7)
			count = random.randint(3, 7)
			
			# Attempt to spawn them
			# We need to find valid ground (Grass)
			# Randomly pick spots
			
			for _ in range(count):
				# Try 5 times to find a spot for this pig
				for attempt in range(5):
					lx = random.randint(0, 15)
					lz = random.randint(0, 15)
					# Find surface Y
					# Start from top of chunk
					found_y = -1
					
					# Optimization: We know chunk height is 16.
					# But we need global Y.
					# cx, cy, cz are chunk indices.
					base_x = cx * 16
					base_y = cy * 16
					base_z = cz * 16
					
					for ly in range(15, -1, -1):
						# We can access chunk directly for speed
						# But using world.get_block_number handles boundaries safely
						b = self.chunks[chunk_position].blocks[lx][ly][lz]
						if b != 0:
							# Found top block
							# Check if it is grass (2) and above is air (likely, since we scan from top)
							if b == 2:
								# Spawn here at ly + 1
								found_y = ly + 1
							break
					
					if found_y != -1:
						# Add to spawn queue
						# Position is global
						spawn_x = base_x + lx + 0.5
						spawn_y = base_y + found_y
						spawn_z = base_z + lz + 0.5
						
						# Check if inside block (safety)
						if spawn_y < base_y + 16:
							self.spawn_queue.append({
								'type': 'pig',
								'pos': (spawn_x, spawn_y, spawn_z)
							})
							break

	def enqueue_mesh_update(self, chunk_position):
		"""Schedule a chunk for mesh update"""
		if chunk_position not in self.chunks:
			return
		if chunk_position in self.mesh_update_set:
			return # Already queued
			
		self.mesh_update_set.add(chunk_position)
		self.mesh_update_queue.append(chunk_position)

	def get_chunk_position(self, position):
		x, y, z = position
		# Optimized bitwise operations for (16, 16, 16) chunk size
		# Standard floor division: y >> 4 is equivalent to floor(y / 16)
		# x >> 4 is x / 16, z >> 4 is z / 16
		return (int(x) >> 4, int(y) >> 4, int(z) >> 4)

	def get_local_position(self, position):
		x, y, z = position
		# Optimized bitwise operations
		# x & 15 is equivalent to x % 16
		# y & 15 is equivalent to y % 16 (since height is now 16)
		return (int(x) & 15, int(y) & 15, int(z) & 15)

	def get_block_number(self, position):
		x, y, z = position
		chunk_position = self.get_chunk_position(position)

		if chunk_position not in self.chunks:
			return 0

		lx, ly, lz = self.get_local_position(position)

		block_number = self.chunks[chunk_position].blocks[lx][ly][lz]
		return block_number

	def is_opaque_block(self, position):
		# get block type and check if it's opaque or not
		# air counts as a transparent block, so test for that too

		block_type = self.block_types[self.get_block_number(position)]

		if not block_type:
			return False

		return not block_type.transparent

	def is_position_loaded(self, position):
		chunk_position = self.get_chunk_position(position)
		return chunk_position in self.chunks

	def get_light(self, position):
		chunk_position = self.get_chunk_position(position)
		if chunk_position not in self.chunks:
			return (0, 15) # Default: No block light, Full skylight (if implicit) or 0? 
			# Design said: SkyLight propagates down. If chunk not loaded, we assume boundary is... tricky.
			# Let's return (0, 0) for safety or (0, 15) if we assume day.
			# Actually, returning 0 is safer to avoid infinite loop of light pouring into void.
			return (0, 0)

		lx, ly, lz = self.get_local_position(position)
		return self.chunks[chunk_position].subchunks[(0, int(ly // 16), 0)].get_light(lx, int(ly % 16), lz)

	def set_light(self, position, block_light, sky_light):
		chunk_position = self.get_chunk_position(position)
		if chunk_position not in self.chunks:
			return

		lx, ly, lz = self.get_local_position(position)
		self.chunks[chunk_position].subchunks[(0, int(ly // 16), 0)].set_light(lx, int(ly % 16), lz, block_light, sky_light)
		self.chunks[chunk_position].modified = True

	def mark_chunk_dirty(self, position):
		chunk_position = self.get_chunk_position(position)
		self.enqueue_mesh_update(chunk_position)


	def set_block(self, position, number):  # set number to 0 (air) to remove block
		x, y, z = position
		chunk_position = self.get_chunk_position(position)

		if chunk_position not in self.chunks:  # if no chunks exist at this position, create a new one
			if number == 0:
				return  # no point in creating a whole new chunk if we're not gonna be adding anything

			self.chunks[chunk_position] = chunk.Chunk(self, chunk_position)

		# Get old block number before changing
		old_block = self.get_block_number(position)
		old_block_type = self.block_types[old_block]
		
		if old_block == number:  # no point updating mesh if the block is the same
			return

		lx, ly, lz = self.get_local_position(position)

		self.chunks[chunk_position].blocks[lx][ly][lz] = number
		self.chunks[chunk_position].modified = True
		
		# LIGHT UPDATE
		new_block_type = self.block_types[number]
		self.light_solver.toggle_light(position, old_block_type, new_block_type)

		self.chunks[chunk_position].update_at_position((x, y, z))
		
		# Immediate update for player interaction responsiveness
		self.chunks[chunk_position].update_mesh()

		cx, cy, cz = chunk_position

		def try_update_chunk_at_position(chunk_position, position):
			if chunk_position in self.chunks:
				self.chunks[chunk_position].update_at_position(position)
				self.chunks[chunk_position].update_mesh()

		if lx == chunk.CHUNK_WIDTH - 1:
			try_update_chunk_at_position((cx + 1, cy, cz), (x + 1, y, z))
		if lx == 0:
			try_update_chunk_at_position((cx - 1, cy, cz), (x - 1, y, z))

		if ly == chunk.CHUNK_HEIGHT - 1:
			try_update_chunk_at_position((cx, cy + 1, cz), (x, y + 1, z))
		if ly == 0:
			try_update_chunk_at_position((cx, cy - 1, cz), (x, y - 1, z))

		if lz == chunk.CHUNK_LENGTH - 1:
			try_update_chunk_at_position((cx, cy, cz + 1), (x, y, z + 1))
		if lz == 0:
			try_update_chunk_at_position((cx, cy, cz - 1), (x, y, z - 1))
		
		# Auto-save the chunk after block change
		# PERFORMANCE FIX: Don't save on every block change, it causes lag.
		# self.save.auto_save_chunk(chunk_position)
		
		# Water simulation triggers
		if number in [8, 9]:  # Water placed
			self.water_simulator.on_water_placed(position)
		elif old_block in [8, 9]:  # Water removed
			self.water_simulator.on_block_removed(position)
		else:  # Other block removed, check if water needs to flow
			self.water_simulator.on_block_removed(position)

	def try_set_block(self, pos, num, collider):
		# if we're trying to remove a block, whatever let it go through

		if not num:
			return self.set_block(pos, 0)

		# make sure the block doesn't intersect with the passed collider

		for block_collider in self.block_types[num].colliders:
			if collider & (block_collider + pos):
				return

		self.set_block(pos, num)

	def draw(self, pass_type='all'):
		# Frustum Culling
		for chunk_position in self.chunks:
			# Calculate Chunk AABB
			cx, cy, cz = chunk_position
			min_x = cx * 16
			min_y = cy * 16
			min_z = cz * 16
			max_x = min_x + 16
			max_y = min_y + 16
			max_z = min_z + 16
			
			if self.frustum.is_box_visible(min_x, min_y, min_z, max_x, max_y, max_z):
				self.chunks[chunk_position].draw(pass_type)

	def update_frustum(self, mvp_matrix):
		self.frustum.update(mvp_matrix)

	def process_chunk_updates(self, position):
		start_time = time.perf_counter()
		
		current_chunk_pos = self.get_chunk_position(position)
		cx, cy, cz = current_chunk_pos
		
		# Only recalculate target set if moved to new chunk
		if current_chunk_pos != self.last_chunk_pos:
			self.last_chunk_pos = current_chunk_pos
			
			# For now, we only care about X and Z for infinite terrain
			render_dist = self.settings.render_distance
	
			# Determine chunks that should be loaded
			self.target_load_set = set()
			for x in range(cx - render_dist, cx + render_dist + 1):
				for z in range(cz - render_dist, cz + render_dist + 1):
					# Load chunks in a vertical slice around the player
					# -2 to +3 covers a reasonable height range around the player
					for y in range(cy - 2, cy + 3):
						self.target_load_set.add((x, y, z))

		# Identify missing chunks
		missing_chunks = []
		# Optimize: Instead of iterating target_set (which can be large), we can check manageable amount?
		# Actually iterating a set of ~500 items is fast (microseconds). 
		# But 'missing_chunks' list creation is fast.
		
		# Prioritize closest chunks?
		# We can just iterate target_set and check.
		for chunk_pos in self.target_load_set:
			if chunk_pos not in self.chunks:
				missing_chunks.append(chunk_pos)

		# Sort missing chunks by distance to player (load closest first)
		if missing_chunks:
			missing_chunks.sort(key=lambda p: (p[0] - cx)**2 + (p[2] - cz)**2)
			
			# Load limited number of chunks per frame to prevent FPS drop
			chunks_loaded_count = 0
			max_chunks_per_frame = 1 # Keep low to prevent stutter
			
			for chunk_pos in missing_chunks:
				if chunks_loaded_count >= max_chunks_per_frame:
					break
					
				self.save.load_chunk(chunk_pos)
				chunks_loaded_count += 1
				
				if chunk_pos in self.chunks:
					# Queue mesh update for self and neighbors
					self.enqueue_mesh_update(chunk_pos)
					
					nx, ny, nz = chunk_pos
					for dx, dy, dz in [(-1,0,0), (1,0,0), (0,0,-1), (0,0,1)]:
						n_pos = (nx + dx, ny + dy, nz + dz)
						self.enqueue_mesh_update(n_pos)
		
		# Process Mesh Update Queue with Time Budget
		# Allow 3ms per frame for mesh updates
		time_budget = 0.003
		
		# LIGHT SYSTEM TICK
		# Process N light steps per frame (Incremental)
		# 1000 steps ~ 1-2ms typically
		self.light_solver.process_queue(budget=1500) 
		
		processed_meshes = 0
		while self.mesh_update_queue:
			if time.perf_counter() - start_time > time_budget:
				break
				
			chunk_pos = self.mesh_update_queue.popleft()
			self.mesh_update_set.discard(chunk_pos)
			
			if chunk_pos in self.chunks:
				# This is the heavy operation
				self.chunks[chunk_pos].update_subchunk_meshes()
				self.chunks[chunk_pos].update_mesh()
				processed_meshes += 1

		# Unload distant chunks
		# Use optimized set cache
		chunks_to_unload = []
		for chunk_pos in self.chunks:
			if chunk_pos not in self.target_load_set:
				chunks_to_unload.append(chunk_pos)
		
		# Unload limited number of chunks per frame
		chunks_unloaded_count = 0
		max_unloads_per_frame = 2
		
		for chunk_pos in chunks_to_unload:
			if chunks_unloaded_count >= max_unloads_per_frame:
				break
			
			# Remove from pending queue if present
			if chunk_pos in self.mesh_update_set:
				try:
					self.mesh_update_queue.remove(chunk_pos)
					self.mesh_update_set.discard(chunk_pos)
				except:
					pass

			# Save before unload if modified
			if self.chunks[chunk_pos].modified:
				self.save.save_chunk(chunk_pos)
			
			# Clean up GPU resources
			self.chunks[chunk_pos].delete()
			del self.chunks[chunk_pos]
			
			chunks_unloaded_count += 1

	def random_tick(self):
		# Perform Minecraft-style random ticks on chunks
		for chunk_pos in list(self.chunks.keys()):
			c = self.chunks[chunk_pos]
			
			# Perform 3 random ticks per chunk (Minecraft standard)
			for _ in range(3):
				lx = random.randint(0, chunk.CHUNK_WIDTH - 1)
				ly = random.randint(0, chunk.CHUNK_HEIGHT - 1)
				lz = random.randint(0, chunk.CHUNK_LENGTH - 1)
				
				block = c.blocks[lx][ly][lz]
				
				if block == 3: # Dirt
					world_pos = (chunk_pos[0]*chunk.CHUNK_WIDTH + lx, 
								 chunk_pos[1]*chunk.CHUNK_HEIGHT + ly, 
								 chunk_pos[2]*chunk.CHUNK_LENGTH + lz)
					
					# Condition 1: Must NOT have an opaque block above
					above_pos = (world_pos[0], world_pos[1] + 1, world_pos[2])
					if not self.is_opaque_block(above_pos):
						# Condition 2: Grass nearby (Optimized)
						# Instead of scanning all 27 neighbors (O(N)), pick ONE random neighbor (O(1))
						# This is how Minecraft does it (random tick checks 1 random neighbor for spread)
						
						dx = random.randint(-1, 1)
						dy = random.randint(-1, 1) # Standard is actually -3 to +1? Simplified to -1, 1
						dz = random.randint(-1, 1)
						
						if dx == 0 and dy == 0 and dz == 0: continue
						
						nx, ny, nz = world_pos[0]+dx, world_pos[1]+dy, world_pos[2]+dz
						if self.get_block_number((nx, ny, nz)) == 2: # Grass found
							# Low chance, but valid spread
							self.set_block(world_pos, 2)


