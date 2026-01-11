import os
import struct
import terrain_generator
import chunk
import random

class Save:
	def __init__(self, world):
		self.world = world
		self.path = "save"
		
		# Ensure save directory exists
		if not os.path.exists(self.path):
			os.makedirs(self.path)
			
		# Load or Create Seed
		self.seed = self.load_seed()
		
		# Initialize generator with the persistent seed
		self.terrain_generator = terrain_generator.TerrainGenerator(seed=self.seed)
		print(f"World Seed: {self.seed}")

	def chunk_position_to_path(self, chunk_position):
		x, y, z = chunk_position
		return f"{self.path}/chunk_{x}_{y}_{z}.bin"
		
	def load_seed(self):
		"""Load seed from file or generate a new one"""
		seed_path = f"{self.path}/seed.bin"
		if os.path.exists(seed_path):
			try:
				with open(seed_path, "rb") as f:
					data = f.read(8)
					if len(data) == 8:
						seed = struct.unpack("q", data)[0] # long long (64 bit)
						return seed
			except Exception as e:
				print(f"Failed to load seed: {e}")
		
		# Generate new seed if not found
		new_seed = random.randint(0, 999999)
		try:
			with open(seed_path, "wb") as f:
				f.write(struct.pack("q", new_seed))
		except Exception as e:
			print(f"Failed to save seed: {e}")
			
		return new_seed

	def load(self):
		# Ensure save directory exists
		if not os.path.exists(self.path):
			os.makedirs(self.path)

	def load_chunk(self, chunk_position):
		chunk_path = self.chunk_position_to_path(chunk_position)
		
		needs_generation = True
		
		# Expected size: 16*16*16
		# If file size is larger (old format 16*32*16), we should probably discard it or migrate.
		# Simplest is to regenerate if size mismatch or just ignore old saves.
		# Given the user request to change height, let's assume we want new generation or migrating.
		# Let's just delete the file if it's old format? Or fail load and regen.
		
		if os.path.exists(chunk_path):
			try:
				with open(chunk_path, "rb") as f:
					# Check for Magic Header for RLE
					header = f.read(4)
					is_rle = (header == b'RLE1')
					
					if is_rle:
						# Expected size for height 16 is 16*16*16 = 4096
						# Old size 16*32*16 = 8192
						# Just checking total blocks isn't enough if RLE matches but dimensions map wrong?
						# Wait, we read RLE count.
						
						total_blocks = chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH
						flat_blocks = []
						
						while len(flat_blocks) < total_blocks:
							pair = f.read(2)
							if not pair or len(pair) < 2:
								break
							count = pair[0]
							block_id = pair[1]
							flat_blocks.extend([block_id] * count)
						
						if len(flat_blocks) != total_blocks:
							print(f"Chunk {chunk_position} corrupted or old version (Length mismatch: {len(flat_blocks)} vs {total_blocks}). Regenerating.")
							needs_generation = True
						else:
							# Reconstruct
							clean_blocks = []
							ptr = 0
							row_k = chunk.CHUNK_LENGTH
							height = chunk.CHUNK_HEIGHT
							width = chunk.CHUNK_WIDTH
							
							for x in range(width):
								col = []
								for y in range(height):
									col.append(flat_blocks[ptr : ptr + row_k])
									ptr += row_k
								clean_blocks.append(col)
								
							new_chunk = chunk.Chunk(self.world, chunk_position)
							new_chunk.blocks = clean_blocks
							self.world.chunks[chunk_position] = new_chunk
							
							# Read Water Levels
							water_count_bytes = f.read(4)
							if water_count_bytes and len(water_count_bytes) == 4:
								water_count = struct.unpack("I", water_count_bytes)[0]
								cx, cy, cz = chunk_position
								base_x = cx * chunk.CHUNK_WIDTH
								base_z = cz * chunk.CHUNK_LENGTH
								metadata = self.world.block_metadata
								set_water = metadata.set_water_level
								water_bytes = f.read(water_count * 5)
								for i in range(water_count):
									off = i * 5
									lx = water_bytes[off]
									ly = int.from_bytes(water_bytes[off+1:off+3], 'little')
									lz = water_bytes[off+3]
									lvl = water_bytes[off+4]
									if ly < chunk.CHUNK_HEIGHT: # Safety check
										set_water((base_x + lx, ly, base_z + lz), lvl)
									
							self.world.light_solver.initialize_sunlight(chunk_position)
							needs_generation = False
					else:
						# Backwards compatibility / Raw format
						# Check file size
						file_size = os.path.getsize(chunk_path)
						expected_size = chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH
						# Rough check (ignoring water metadata which might be appended)
						
						if file_size < expected_size:
							print(f"Chunk {chunk_position} raw size mismatch. Regenerating.")
							needs_generation = True
						else:
							# Legacy load might crash if dimensions changed.
							# Safe bet: If not RLE, just regenerate to be safe with new height.
							# Or try to read exactly N bytes
							f.seek(0)
							raw_blocks = f.read(expected_size)
							if len(raw_blocks) == expected_size:
								clean_blocks = []
								ptr = 0
								row_k = chunk.CHUNK_LENGTH
								for x in range(chunk.CHUNK_WIDTH):
									col = []
									for y in range(chunk.CHUNK_HEIGHT):
										col.append(list(raw_blocks[ptr : ptr + row_k]))
										ptr += row_k
									clean_blocks.append(col)
								
								new_chunk = chunk.Chunk(self.world, chunk_position)
								new_chunk.blocks = clean_blocks
								self.world.chunks[chunk_position] = new_chunk
								
								# Water...
								water_count_bytes = f.read(4)
								if water_count_bytes and len(water_count_bytes) == 4:
									water_count = struct.unpack("I", water_count_bytes)[0]
									cx, cy, cz = chunk_position
									base_x = cx * chunk.CHUNK_WIDTH
									base_z = cz * chunk.CHUNK_LENGTH
									metadata = self.world.block_metadata
									set_water = metadata.set_water_level
									water_bytes = f.read(water_count * 5)
									for i in range(water_count):
										off = i * 5
										lx = water_bytes[off]
										ly = int.from_bytes(water_bytes[off+1:off+3], 'little')
										lz = water_bytes[off+3]
										lvl = water_bytes[off+4]
										if ly < chunk.CHUNK_HEIGHT:
											set_water((base_x + lx, ly, base_z + lz), lvl)
								
								self.world.light_solver.initialize_sunlight(chunk_position)
								needs_generation = False
							else:
								needs_generation = True

			except Exception as e:
				print(f"Failed to load binary chunk {chunk_position}: {e}")
				needs_generation = True

		if needs_generation:
			# Generate new chunk
			blocks = self.terrain_generator.generate_chunk_blocks(chunk_position)
			
			if blocks:
				new_chunk = chunk.Chunk(self.world, chunk_position)
				new_chunk.blocks = blocks
				self.world.chunks[chunk_position] = new_chunk
				
				# Initialize Sunlight
				self.world.light_solver.initialize_sunlight(chunk_position)
				
				# Spawn Mobs (Pig Colonies)
				self.world.spawn_pigs_in_chunk(chunk_position)
				
				new_chunk.modified = True
				
				# Immediate Save to prevent re-generation lag on next load/restart
				self.save_chunk(chunk_position)

	def save_chunk(self, chunk_position):
		if chunk_position not in self.world.chunks:
			return
			
		chunk_obj = self.world.chunks[chunk_position]
		chunk_path = self.chunk_position_to_path(chunk_position)
		
		try:
			with open(chunk_path, "wb") as f:
				# --- RLE Compression ---
				f.write(b'RLE1') # Magic Header
				
				# Flatten loop for RLE
				# We compress strictly in x -> y -> z order
				
				current_block = -1
				count = 0
				
				# Buffering writes slightly for performance, or write directly? 
				# Bytearray is faster.
				rle_data = bytearray()
				
				for col in chunk_obj.blocks: # x
					for row in col: # y
						for block_id in row: # z
							if block_id == current_block and count < 255:
								count += 1
							else:
								if count > 0:
									rle_data.append(count)
									rle_data.append(current_block)
								current_block = block_id
								count = 1
				
				# Write final group
				if count > 0:
					rle_data.append(count)
					rle_data.append(current_block)
					
				f.write(rle_data)
				
				# --- Write Water Levels ---
				water_entries = bytearray()
				count = 0
				
				cx, cy, cz = chunk_position
				base_x = cx * chunk.CHUNK_WIDTH
				base_z = cz * chunk.CHUNK_LENGTH
				
				block_metadata_obj = self.world.block_metadata
				
				for lx in range(chunk.CHUNK_WIDTH):
					for ly in range(chunk.CHUNK_HEIGHT):
						for lz in range(chunk.CHUNK_LENGTH):
							block_id = chunk_obj.blocks[lx][ly][lz]
							if block_id == 8 or block_id == 9: # Water
								lvl = block_metadata_obj.get_water_level((base_x + lx, ly, base_z + lz))
								# Entry: x(1B), y(2B), z(1B), lvl(1B)
								water_entries.append(lx)
								water_entries.extend(ly.to_bytes(2, 'little'))
								water_entries.append(lz)
								water_entries.append(lvl)
								count += 1
				
				f.write(struct.pack("I", count))
				f.write(water_entries)
				
				chunk_obj.modified = False
				
		except Exception as e:
			print(f"Failed to save binary chunk {chunk_position}: {e}")

	def auto_save_chunk(self, chunk_position):
		if chunk_position in self.world.chunks:
			self.save_chunk(chunk_position)

	def save(self):
		print("Saving world...")
		saved_count = 0
		for chunk_position in self.world.chunks:
			if self.world.chunks[chunk_position].modified:
				self.save_chunk(chunk_position)
				saved_count += 1
		print(f"World saved ({saved_count} chunks updated).")

	def save_player(self, player):
		try:
			path = f"{self.path}/player.bin"
			with open(path, "wb") as f:
				bg_data = struct.pack("ddddd", 
					player.position[0], player.position[1], player.position[2],
					player.rotation[0], player.rotation[1]
				)
				f.write(bg_data)
		except Exception as e:
			print(f"Failed to save player: {e}")

	def load_player(self, player):
		path = f"{self.path}/player.bin"
		if not os.path.exists(path):
			return False
		
		try:
			with open(path, "rb") as f:
				data = f.read(5 * 8) # 5 doubles * 8 bytes
				if len(data) == 40:
					unpacked = struct.unpack("ddddd", data)
					player.position = list(unpacked[0:3])
					player.rotation = list(unpacked[3:5])
					return True
		except Exception as e:
			print(f"Failed to load player: {e}")
		return False

	def save_mobs(self, mobs_data):
		import pickle
		try:
			path = f"{self.path}/mobs.dat"
			with open(path, "wb") as f:
				pickle.dump(mobs_data, f)
		except Exception as e:
			print(f"Failed to save mobs: {e}")

	def load_mobs(self):
		import pickle
		path = f"{self.path}/mobs.dat"
		if not os.path.exists(path):
			return {}
		try:
			with open(path, "rb") as f:
				return pickle.load(f)
		except Exception as e:
			print(f"Failed to load mobs: {e}")
			return {}
