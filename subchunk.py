SUBCHUNK_WIDTH = 16
SUBCHUNK_HEIGHT = 16
SUBCHUNK_LENGTH = 16


class Subchunk:
	def __init__(self, parent, subchunk_position):
		self.parent = parent
		self.world = self.parent.world

		self.subchunk_position = subchunk_position

		self.local_position = (
			self.subchunk_position[0] * SUBCHUNK_WIDTH,
			self.subchunk_position[1] * SUBCHUNK_HEIGHT,
			self.subchunk_position[2] * SUBCHUNK_LENGTH,
		)

		self.position = (
			self.parent.position[0] + self.local_position[0],
			self.parent.position[1] + self.local_position[1],
			self.parent.position[2] + self.local_position[2],
		)

		# mesh variables

		self.mesh_vertex_positions = []
		self.mesh_tex_coords = []
		self.mesh_shading_values = []

		self.mesh_index_counter = 0
		self.mesh_indices = []

		# Water mesh variables
		self.water_mesh_vertex_positions = []
		self.water_mesh_tex_coords = []
		self.water_mesh_shading_values = []
		self.water_mesh_index_counter = 0
		self.water_mesh_indices = []

		# LIGHT SYSTEM: Packed SkyLight (4 bits) | BlockLight (4 bits)
		# Default 0 (Darkness). Sunlight initialization will happen elsewhere.
		self.light_map = bytearray(SUBCHUNK_WIDTH * SUBCHUNK_HEIGHT * SUBCHUNK_LENGTH)

	def update_mesh(self, update_only_water=False):
		# Setup lists
		if not update_only_water:
			self.mesh_vertex_positions = []
			self.mesh_tex_coords = []
			self.mesh_shading_values = []
			self.mesh_index_counter = 0
			self.mesh_indices = []

		self.water_mesh_vertex_positions = []
		self.water_mesh_tex_coords = []
		self.water_mesh_shading_values = []
		self.water_mesh_index_counter = 0
		self.water_mesh_indices = []

		# Local Caching for Speed
		blocks = self.parent.blocks
		world_block_types = self.world.block_types
		world = self.world
		
		# Pre-compute transparency lookups to avoid object attribute access in loop
		# usage: transparent_lookup[block_number] -> bool
		max_block_id = len(world_block_types)
		transparent_lookup = [False] * max_block_id
		glass_lookup = [False] * max_block_id
		
		# Assumes block_types list is contiguous key=index
		# We need to handle the fact that block_types can grow. 
		# But here we just take current world state.
		for i, bt in enumerate(world_block_types):
			if bt:
				transparent_lookup[i] = bt.transparent
				glass_lookup[i] = bt.glass
		
		# Explicitly handling air (0) is implicit if we check 'if neighbor_num:' 
		# but usually we want is_transparent(0) -> True.
		# Let's handle 0 separately in logic or assume 0 is not in lists (0 used as index 0 of lists?)
		# world.block_types[0] is None usually? Check world.py. Yes, [None].
		# So transparent_lookup[0] is False (based on init), but air IS transparent.
		# We'll just define logic: if neighbor == 0: visible = True.

		sx, sy, sz = self.position
		lx_offset, ly_offset, lz_offset = self.local_position
		
		CHUNK_W = 16
		CHUNK_H = 16
		CHUNK_L = 16

		# Directions for 6 faces: Right, Left, Top, Bottom, Front, Back
		# corresponding to indices 0, 1, 2, 3, 4, 5
		faces_dir = [
			(1, 0, 0),  # Right
			(-1, 0, 0), # Left
			(0, 1, 0),  # Top
			(0, -1, 0), # Bottom
			(0, 0, 1),  # Front
			(0, 0, -1)  # Back
		]

		# Lists to append to (locals are faster)
		solid_verts = self.mesh_vertex_positions
		solid_tex = self.mesh_tex_coords
		solid_shade = self.mesh_shading_values
		solid_ind = self.mesh_indices
		
		water_verts = self.water_mesh_vertex_positions
		water_tex = self.water_mesh_tex_coords
		water_shade = self.water_mesh_shading_values
		water_ind = self.water_mesh_indices

		# Iterate blocks
		for local_x in range(SUBCHUNK_WIDTH):
			parent_lx = lx_offset + local_x
			gx = sx + local_x
			
			for local_y in range(SUBCHUNK_HEIGHT):
				parent_ly = ly_offset + local_y
				gy = sy + local_y
				
				for local_z in range(SUBCHUNK_LENGTH):
					parent_lz = lz_offset + local_z
					
					block_number = blocks[parent_lx][parent_ly][parent_lz]

					if not block_number:
						continue

					# Determine if water
					is_water = (block_number == 8 or block_number == 9)
					
					if update_only_water and not is_water:
						continue
					
					# Select buffers
					if is_water:
						current_verts = water_verts
						current_tex = water_tex
						current_shade = water_shade
						current_ind = water_ind
						# We track counter manually
						# base_index = self.water_mesh_index_counter 
						# But we need to update 'self' counter at end of face add? 
						# Or just use len(current_verts)//3
						base_index = len(current_verts) // 3
					else:
						# If update_only_water is True, we skipped above.
						current_verts = solid_verts
						current_tex = solid_tex
						current_shade = solid_shade
						current_ind = solid_ind
						base_index = len(current_verts) // 3

					block_type_data = world_block_types[block_number]
					is_glass = glass_lookup[block_number]
					is_cube = block_type_data.is_cube
					
					gz = sz + local_z # Recalculate or use loop var? Loop var safe.

					# Check 6 faces
					for face_idx in range(6):
						dx, dy, dz = faces_dir[face_idx]
						
						# Neighbor position
						nlx, nly, nlz = parent_lx + dx, parent_ly + dy, parent_lz + dz
						
						# Visibility check
						visible = True
						if is_cube:
							# Check neighbor
							# Fast path: Inside chunk
							if 0 <= nlx < CHUNK_W and 0 <= nly < CHUNK_H and 0 <= nlz < CHUNK_L:
								n_num = blocks[nlx][nly][nlz]
								if n_num:
									if is_glass and n_num == block_number:
										visible = False
									elif not transparent_lookup[n_num]:
										visible = False
								# else n_num == 0 (Air) -> Visible = True
							else:
								# Slow path: Boundary check
								# Use global coord
								n_pos = (gx + dx, gy + dy, gz + dz)
								if world.is_opaque_block(n_pos):
									visible = False
								elif is_glass and world.get_block_number(n_pos) == block_number:
									visible = False
						
						# Non-cube blocks (like plants) render all faces usually?
						# Or just logic: if not is_cube, render all 6? 
						# Original code: if not cube, iterate len(vertex_positions) which might be != 6 faces.
						# Wait, original code: if not is_cube: add_face(i) for i in range...
						# We handled is_cube check. If not cube, we break this loop and do special handling?
						
						if not is_cube:
							break # Handle at end

						if visible:
							# Add Face Logic Inlined
							# Geometry
							v_pos = block_type_data.vertex_positions[face_idx].copy() # 12 floats
							
							# Water logic
							if is_water:
								# ... (Keep existing water logic, it's complex but needed)
								pass 
								# NOTE: For brevity and performance I'll implement simplified or call helper if water
								# Re-implementing simplified height logic here:
								if face_idx == 2: # Top
									level = world.block_metadata.get_water_level((gx, gy, gz))
									corners = [
										[(gx+1, gy, gz), (gx, gy, gz+1), (gx+1, gy, gz+1)],
										[(gx+1, gy, gz), (gx, gy, gz-1), (gx+1, gy, gz-1)],
										[(gx-1, gy, gz), (gx, gy, gz-1), (gx-1, gy, gz-1)],
										[(gx-1, gy, gz), (gx, gy, gz+1), (gx-1, gy, gz+1)]
									]
									for c_i in range(4):
										y_ind = c_i * 3 + 1
										h_sum = max(0.1, 1.0 - (level / 5.0) ** 1.5) if level else 1.0
										count = 1
										for np in corners[c_i]:
											nb = world.get_block_number(np)
											if nb == 8 or nb == 9:
												nl = world.block_metadata.get_water_level(np)
												h_sum += max(0.1, 1.0 - (nl / 5.0) ** 1.5) if nl else 1.0
												count += 1
										
										height_factor = h_sum / count
										# Fix for centered coordinates (-0.5 to 0.5)
										v_pos[y_ind] = (v_pos[y_ind] + 0.5) * height_factor - 0.5
								else:
									level = world.block_metadata.get_water_level((gx, gy, gz))
									mult = max(0.1, 1.0 - (level / 5.0) ** 1.5) if level else 1.0
									# Fix for centered coordinates (-0.5 to 0.5)
									# Apply to all 4 Y-coordinates of the face
									for yi in [1, 4, 7, 10]:
										v_pos[yi] = (v_pos[yi] + 0.5) * mult - 0.5

							# Apply translation
							# x, y, z = gx, gy, gz
							# v_pos layout: x,y,z, x,y,z, ...
							v_pos[0::3] = [v + gx for v in v_pos[0::3]]
							v_pos[1::3] = [v + gy for v in v_pos[1::3]]
							v_pos[2::3] = [v + gz for v in v_pos[2::3]]
							
							current_verts.extend(v_pos)
							
							# Indices
							# 0, 1, 2, 0, 2, 3
							current_ind.extend([base_index, base_index+1, base_index+2, base_index, base_index+2, base_index+3])
							base_index += 4
							
							current_tex.extend(block_type_data.tex_coords[face_idx])
							
							# LIGHTING LOGIC
							# Calculate neighbor local position relative to subchunk
							# local_x, local_y, local_z are current block's local coords in subchunk
							nl_x = local_x + dx
							nl_y = local_y + dy
							nl_z = local_z + dz
							
							light_level = 0
							if 0 <= nl_x < 16 and 0 <= nl_y < 16 and 0 <= nl_z < 16:
								# Neighbor is in this subchunk
								l_vals = self.get_light(nl_x, nl_y, nl_z)
								light_level = max(l_vals[0], l_vals[1])
							else:
								# Neighbor is outside, ask world (global coords)
								l_vals = world.get_light((gx + dx, gy + dy, gz + dz))
								light_level = max(l_vals[0], l_vals[1])
								
							if self.mesh_index_counter == 0 and light_level == 0:
								# Print once per update to avoid spam, but only if dark
								pass

							light_factor = light_level / 15.0
							
							# Apply light_factor to static shading values
							base_shading = block_type_data.shading_values[face_idx]
							mod_shading = [s * light_factor for s in base_shading]
							
							current_shade.extend(mod_shading)

					# End Face Loop
					
					if not is_cube:
						# Special handling for non-cubes (plants, x-shapes)
						# Iterate all defined faces in model
						model_faces = len(block_type_data.vertex_positions)
						for f_i in range(model_faces):
							v_pos = block_type_data.vertex_positions[f_i].copy()
							v_pos[0::3] = [v + gx for v in v_pos[0::3]]
							v_pos[1::3] = [v + gy for v in v_pos[1::3]]
							v_pos[2::3] = [v + gz for v in v_pos[2::3]]
							
							if is_water:
								current_verts = water_verts; current_tex = water_tex; current_shade = water_shade; current_ind = water_ind
								bi = len(current_verts) // 3
							else:
								current_verts = solid_verts; current_tex = solid_tex; current_shade = solid_shade; current_ind = solid_ind
								bi = len(current_verts) // 3

							current_verts.extend(v_pos)
							current_ind.extend([bi, bi+1, bi+2, bi, bi+2, bi+3])
							current_tex.extend(block_type_data.tex_coords[f_i])
							
							# LIGHTING LOGIC (Center block)
							l_vals = self.get_light(local_x, local_y, local_z)
							light_level = max(l_vals[0], l_vals[1])
							light_factor = light_level / 15.0
							
							base_shading = block_type_data.shading_values[f_i]
							mod_shading = [s * light_factor for s in base_shading]
							current_shade.extend(mod_shading)

		# Finalize counters
		self.mesh_index_counter = len(self.mesh_indices)
		self.water_mesh_index_counter = len(self.water_mesh_indices)

	def get_light(self, lx, ly, lz):
		# Returns (block_light, sky_light)
		# Indexing: x * 256 + y * 16 + z
		index = lx * 256 + ly * 16 + lz
		val = self.light_map[index]
		return val & 0xF, (val >> 4) & 0xF

	def set_light(self, lx, ly, lz, block_light, sky_light):
		index = lx * 256 + ly * 16 + lz
		self.light_map[index] = (int(sky_light) << 4) | (int(block_light) & 0xF)


