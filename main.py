import ctypes
import math
import random
import pyglet

pyglet.options["shadow_window"] = False
pyglet.options["debug_gl"] = False

import pyglet.gl as gl

import shader
import player
import matrix


import chunk
import world
import collider

import hit
import particles
import inventory
import gui
import dropped_item
import mob
import pig



import os
import pyglet.media as media
import item_model

class SoundManager:
	def __init__(self):
		self.sounds = {}
		self.sound_dir = "sound"
		self.load_sounds()

	def load_sounds(self):
		if not os.path.exists(self.sound_dir):
			print(f"Sound directory {self.sound_dir} not found.")
			return

		# Load root sounds
		for filename in os.listdir(self.sound_dir):
			if filename.endswith(".ogg"):
				name = filename[:-4]
				path = os.path.join(self.sound_dir, filename)
				try:
					self.sounds[name] = media.load(path, streaming=False)
				except Exception as e:
					print(f"Failed to load sound {filename}: {e}")

		# Load pig sounds
		pig_dir = os.path.join(self.sound_dir, "pig")
		if os.path.exists(pig_dir):
			for filename in os.listdir(pig_dir):
				if filename.endswith(".ogg"):
					name = f"pig_{filename[:-4]}"
					path = os.path.join(pig_dir, filename)
					try:
						self.sounds[name] = media.load(path, streaming=False)
					except Exception as e:
						print(f"Failed to load pig sound {filename}: {e}")

	def update_listener(self, position, rotation):
		# pyglet listener
		try:
			listener = media.get_audio_driver().get_listener()
			listener.position = position
			# rotation is (yaw, pitch)
			# direction vector
			yaw, pitch = rotation
			fx = math.cos(yaw) * math.cos(pitch)
			fy = math.sin(pitch)
			fz = math.sin(yaw) * math.cos(pitch)
			listener.forward_orientation = (fx, fy, fz)
			listener.up_orientation = (0, 1, 0)
		except:
			pass

	def play(self, sound_name, position=None):
		if not sound_name:
			return
		
		# If it's a generic sound name, pick one of the variations
		if sound_name in ["stone", "grass", "sand", "wood", "gravel", "snow", "cloth", "coral", "wet_grass"]:
			variation = random.randint(1, 4)
			actual_name = f"{sound_name}{variation}"
		elif sound_name == "pig_say":
			variation = random.randint(1, 3)
			actual_name = f"pig_say{variation}"
		elif sound_name == "pig_step":
			variation = random.randint(1, 5)
			actual_name = f"pig_step{variation}"
		else:
			actual_name = sound_name

		if actual_name in self.sounds:
			try:
				player = self.sounds[actual_name].play()
				if position:
					player.position = position
					player.min_distance = 2.0
					player.max_distance = 32.0
			except Exception as e:
				# print(f"Error playing sound {actual_name}: {e}")
				pass

class Window(pyglet.window.Window):
	def __init__(self, **args):
		super().__init__(**args)

		# create world

		self.world = world.World()

		# create shader

		self.shader = shader.Shader("vert.glsl", "frag.glsl")
		self.shader_sampler_location = self.shader.find_uniform(b"texture_array_sampler")
		self.shader_alpha_factor_location = self.shader.find_uniform(b"alpha_factor")
		self.shader.use()
		
		# Overlay shader
		self.overlay_shader = shader.Shader("overlay_vert.glsl", "overlay_frag.glsl")
		self.overlay_color_loc = self.overlay_shader.find_uniform(b"color")
		
		# Initialize GPU Water Simulator (OpenGL context is now ready)
		import water_simulator
		self.world.water_simulator = water_simulator.WaterSimulatorGPU(self.world)
		
		# Overlay Quad
		self.overlay_vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.overlay_vao)
		gl.glBindVertexArray(self.overlay_vao)
		
		quad_verts = [-1.0, -1.0,  1.0, -1.0,  1.0, 1.0,  -1.0, 1.0]
		self.overlay_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.overlay_vbo)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.overlay_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(quad_verts)*4, (gl.GLfloat * len(quad_verts))(*quad_verts), gl.GL_STATIC_DRAW)
		
		gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		# Crosshair VAO/VBO
		self.crosshair_vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.crosshair_vao)
		gl.glBindVertexArray(self.crosshair_vao)
		
		self.crosshair_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.crosshair_vbo)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.crosshair_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, 8 * 4, None, gl.GL_DYNAMIC_DRAW) # 4 verts * 2 floats
		
		gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)
		
		# pyglet stuff

		pyglet.clock.schedule_interval(self.update, 1.0 / 60)
		self.mouse_captured = False

		# player stuff

		self.player = player.Player(self.world, self.shader, self.width, self.height)

		# misc stuff

		self.holding = 44  # 5
		
		# Hand rendering variables
		self.hand_vao = gl.GLuint(0)
		self.hand_vbo = gl.GLuint(0)
		self.hand_ibo = gl.GLuint(0)
		self.hand_vertex_count = 0
		
		# Hand animation variables
		self.hand_sway_x = 0.0
		self.hand_sway_y = 0.0
		self.hand_bob_timer = 0.0
		self.mouse_dx = 0.0
		self.mouse_dy = 0.0
		
		self.hand_swing = 0.0  # Animation progress
		self.is_swinging = False # One-shot swing (placing/striking)
		
		# Third Person Block Rendering
		self.third_person_block_vao = gl.GLuint(0)
		self.third_person_block_vbo = gl.GLuint(0)
		self.third_person_block_ibo = gl.GLuint(0)
		self.third_person_block_vertex_count = 0
		gl.glGenVertexArrays(1, self.third_person_block_vao)
		gl.glGenBuffers(1, self.third_person_block_vbo)
		gl.glGenBuffers(1, self.third_person_block_ibo)
		
		# Empty Hand (Arm) Rendering
		self.empty_hand_vao = gl.GLuint(0)
		self.empty_hand_vbo = gl.GLuint(0)
		self.empty_hand_vertex_count = 0
		self.empty_hand_texture = None
		gl.glGenVertexArrays(1, self.empty_hand_vao)
		gl.glGenBuffers(1, self.empty_hand_vbo)
		self.init_empty_hand_mesh()
		
		gl.glGenVertexArrays(1, self.hand_vao)
		gl.glGenBuffers(1, self.hand_vbo)
		gl.glGenBuffers(1, self.hand_ibo)
		
		self.update_hand_mesh()
		
		# Try to load player state
		if not self.world.save.load_player(self.player):
			# New game: Find safe spawn
			print("Finding safe spawn point...")
			spawn_found = False
			for r in range(0, 100, 10): # Search radius
				if spawn_found: break
				
				# Try a few points in this radius
				points = [(r, 0), (-r, 0), (0, r), (0, -r)]
				for px, pz in points:
					# Find highest block
					for y in range(chunk.CHUNK_HEIGHT - 2, 0, -1):
						# Check if safe: Block at y is solid, y+1 and y+2 are air
						block_below = self.world.get_block_number((px, y, pz))
						block_at = self.world.get_block_number((px, y+1, pz))
						block_above = self.world.get_block_number((px, y+2, pz))
						
						if block_below != 0 and block_at == 0 and block_above == 0:
							# Found safe spot!
							self.player.teleport((px, y + 2, pz))
							spawn_found = True
							print(f"Spawned at {px}, {y+2}, {pz}")
							break
					if spawn_found: break
			
			if not spawn_found:
				# Fallback
				self.player.teleport((0, 80, 0))
		
		# Auto-save every 60 seconds
		pyglet.clock.schedule_interval(self.auto_save, 60.0)
		
		# Block Breaking State
		self.breaking_block = False
		self.breaking_pos = None
		self.breaking_progress = 0.0
		self.breaking_hardness = 0.1
		self.breaking_last_update = 0

		# VAO for breaking overlay
		self.breaking_vao = gl.GLuint(0)
		self.breaking_vbo = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.breaking_vao)
		gl.glGenBuffers(1, self.breaking_vbo)
		
		# Particle System
		self.particle_system = particles.ParticleSystem(self.shader)
		self.digging_particle_timer = 0
		
		# Inventory System
		self.inventory = inventory.Inventory()
		self.inventory.load() # Load saved inventory
		self.gui = gui.InventoryRenderer(self.inventory, self.world, self.width, self.height)

		# Dropped Items
		self.dropped_items = []
		
		# Mobs
		self.mobs = []

		# Camera State
		
		# Player Model (Steve)
		# We use the Mob class but manage it manually
		self.steve = mob.Mob(self.world, self.player.position)
		self.steve.gravity_enabled = False # We control position manually

		# Sound System
		self.sound_manager = SoundManager()
		self.world.sound_manager = self.sound_manager
		self.walk_sound_timer = 0.0
		self.break_sound_timer = 0.0
		self.item_model_cache = {}
		self.item_transforms = {}
		if os.path.exists("data/item_transforms.json"):
			try:
				with open("data/item_transforms.json", "r") as f:
					self.item_transforms = json.load(f)
			except: pass
			self.last_transforms_mtime = os.path.getmtime("data/item_transforms.json")
		else:
			self.last_transforms_mtime = 0
		
		# Schedule hot reload check
		pyglet.clock.schedule_interval(self.check_hot_reload, 1.0)

	def auto_save(self, dt):
		self.world.save.save()
		self.world.save.save_player(self.player)
		
		# Save Mobs (Active + Persistent)
		# Create a snapshot of all mobs
		all_mobs = self.world.persistent_mobs.copy()
		
		# Add active mobs to the snapshot
		for m in self.mobs:
			cpos = self.world.get_chunk_position(m.position)
			data = {
				'position': list(m.position),
				'rotation': list(m.rotation),
				'ai_state': m.ai_state,
				'type': 'pig' if isinstance(m, pig.Pig) else 'mob',
				'health': m.health
			}
			if cpos not in all_mobs:
				all_mobs[cpos] = []
			all_mobs[cpos].append(data)
			
		self.world.save.save_mobs(all_mobs)

	def update(self, delta_time):
		# Process Spawn Queue from World
		if hasattr(self.world, 'spawn_queue'):
			while self.world.spawn_queue:
				data = self.world.spawn_queue.popleft()
				if data['type'] == 'pig':
					try:
						p = pig.Pig(self.world, position=data['pos'])
						# Inject player ref for AI
						p.player = self.player 
						p.sound_manager = self.sound_manager
						self.mobs.append(p)
						# print(f"Spawned Pig at {data['pos']}") 
					except Exception as e:
						print(f"Failed to spawn pig: {e}")

		# Sync Steve Model with Player
		self.steve.position = list(self.player.position)
		
		# Fix: Steve Yaw (Horizontal) - Character faces SAME WAY as CAMERA
		self.steve.rotation[0] = self.player.rotation[0] + math.pi / 2
		
		# Fix: Steve Head Pitch (Vertical)
		self.steve.head.rotation[0] = -self.player.rotation[1]
		
		# Animation State
		# 1. Mining/Swinging Animation (Priority)
		if self.breaking_block or self.is_swinging:
			if not hasattr(self.steve, 'mine_time'): self.steve.mine_time = 0.0
			self.steve.mine_time += delta_time * 18
			# Swing arm forward and back
			swing = -math.sin(self.steve.mine_time) * 0.6 - 0.2
			self.steve.r_arm.rotation[0] = swing
		else:
			if hasattr(self.steve, 'mine_time'): 
				self.steve.mine_time = 0.0
			
		# 2. Walk Animation
		if self.player.input[0] != 0 or self.player.input[2] != 0:
			# Slower animation when crouching
			anim_speed = 6 if self.player.crouching else 12
			self.steve.anim_time += delta_time * anim_speed
			
			# Smaller leg swing when crouching
			leg_amplitude = 0.4 if self.player.crouching else 0.7
			angle = math.sin(self.steve.anim_time) * leg_amplitude
			
			# Leg Animation (Always)
			self.steve.r_leg.rotation[0] = -angle
			self.steve.l_leg.rotation[0] = angle
			
			# Arm Animation (Only if not mining/swinging)
			if not (self.breaking_block or self.is_swinging):
				self.steve.r_arm.rotation[0] = angle
				self.steve.l_arm.rotation[0] = -angle
			else:
				# Mining overrides right arm, but left arm still swings
				self.steve.l_arm.rotation[0] = -angle
		else:
			# Reset limbs when idle - Smooth Interp
			speed = 10.0 * delta_time
			if not (self.breaking_block or self.is_swinging):
				self.steve.r_arm.rotation[0] *= max(0, 1.0 - speed)
			self.steve.l_arm.rotation[0] *= max(0, 1.0 - speed)
			self.steve.r_leg.rotation[0] *= max(0, 1.0 - speed)
			self.steve.l_leg.rotation[0] *= max(0, 1.0 - speed)
			
			# Snap to 0 if very small
			if abs(self.steve.r_leg.rotation[0]) < 0.01:
				if not (self.breaking_block or self.is_swinging): self.steve.r_arm.rotation[0] = 0
				self.steve.l_arm.rotation[0] = 0
				self.steve.r_leg.rotation[0] = 0
				self.steve.l_leg.rotation[0] = 0

		# 3. Crouching Animation
		if not hasattr(self.steve, 'crouch_amount'): self.steve.crouch_amount = 0.0
		
		target_crouch = 0.3 if self.player.crouching else 0.0
		lerp_speed = 10.0 * delta_time
		self.steve.crouch_amount += (target_crouch - self.steve.crouch_amount) * min(1.0, lerp_speed)
		
		# Apply crouch: Tilt body forward and lower position
		self.steve.body.rotation[0] = self.steve.crouch_amount
		self.steve.head.position[1] = 24 * 0.06 - self.steve.crouch_amount * 0.15
		self.steve.position[1] = self.player.position[1] - self.steve.crouch_amount * 0.5  # Lowered more
		
		# Move body down into legs when crouching
		ps = 0.06
		self.steve.body.position[1] = 24*ps - self.steve.crouch_amount * 0.12  # Body goes down into legs
		
		# Legs rotate forward to compensate for body tilt (stay connected)
		# When body tilts forward, legs need to rotate backward by the same amount to stay vertical
		leg_compensation = -self.steve.crouch_amount
		
		# Only apply when not walking (walking animation overrides)
		if self.player.crouching and not (self.player.input[0] != 0 or self.player.input[2] != 0):
			self.steve.r_leg.rotation[0] = leg_compensation
			self.steve.l_leg.rotation[0] = leg_compensation
		
		# Adjust leg positions to follow body pivot (move backward with body)
		ps = 0.06
		leg_offset_z = -self.steve.crouch_amount * 0.6  # Negative = backward
		self.steve.r_leg.position[2] = leg_offset_z
		self.steve.l_leg.position[2] = leg_offset_z

		# Update title with FPS
		fps = 1.0 / delta_time if delta_time > 0 else 0
		self.set_caption(f"PythonCraft v8.0 - FPS: {fps:.2f}")

		# Hand Animation Logic
		# Swing
		if self.breaking_block or self.is_swinging:
			# Reduced speed for a more natural single-swing feel
			self.hand_swing += delta_time * 12 
			
			if self.is_swinging and self.hand_swing >= math.pi:
				self.is_swinging = False
				if not self.breaking_block:
					self.hand_swing = 0.0
			
			# Keep swing value circular during continuous breaking to allow quick stopping
			if self.breaking_block and self.hand_swing > math.pi * 2:
				self.hand_swing %= (math.pi * 2)
		else:
			# Smoothly return to 0 if not breaking
			if self.hand_swing > 0:
				self.hand_swing -= delta_time * 20
				if self.hand_swing < 0: self.hand_swing = 0.0

		# Bobbing
		# Check if moving (WASD) and not flying
		is_moving = False
		if self.mouse_captured:
			if self.player.input[0] != 0 or self.player.input[2] != 0:
				is_moving = True
		
		if is_moving: # and not self.player.flying: # Simplification: bob even if flying for now or check flying
			# Adjust bobbing speed based on player movement state
			bob_speed = 10
			if self.player.sprinting:
				bob_speed = 15
			elif self.player.crouching:
				bob_speed = 5
				
			self.hand_bob_timer += delta_time * bob_speed

			# Walk Sound Logic
			if self.player.grounded and not self.player.flying:
				# Determine interval
				interval = 0.35
				if self.player.sprinting:
					interval = 0.25
				elif self.player.crouching:
					interval = 0.5
					
				self.walk_sound_timer += delta_time
				if self.walk_sound_timer >= interval:
					self.walk_sound_timer = 0
					# Get block below
					bx, by, bz = map(math.floor, [self.player.position[0], self.player.position[1]-0.1, self.player.position[2]])
					block_below = self.world.get_block_number((bx, by, bz))
					if block_below:
						sound_type = self.world.block_types[block_below].sound
						self.sound_manager.play(sound_type, position=(bx+0.5, by+0.5, bz+0.5))
		else:
			# Reset to 0 smoothly or just snap. Snapping is safer for now to avoid drifting.
			self.hand_bob_timer = 0
			self.walk_sound_timer = 0 # reset when stopped
			
		# Block Breaking Logic
		if self.breaking_block:
			# Check if we are still looking at the same block
			hit_result_block = None
			hit_pos = None
			
			def hit_callback(current_block, next_block):
				nonlocal hit_result_block
				hit_result_block = next_block
				return True

			x, y, z = self.player.position
			y += self.player.eyelevel
			hit_ray = hit.Hit_ray(self.world, self.player.rotation, (x, y, z))
			
			while hit_ray.distance < hit.HIT_RANGE:
				if hit_ray.step(hit_callback):
					hit_pos = hit_ray.position
					break
			
			if hit_result_block != self.breaking_pos:
				# Stopped looking at block
				self.breaking_block = False
				self.breaking_progress = 0.0
				self.break_sound_timer = 0.0
			else:
				# Continue breaking
				self.breaking_progress += delta_time
				
				# Break Sound Logic
				self.break_sound_timer += delta_time
				if self.break_sound_timer >= 0.25:
					self.break_sound_timer = 0
					# Play digging sound for the block being broken
					block_num = self.world.get_block_number(self.breaking_pos)
					if block_num:
						sound_type = self.world.block_types[block_num].sound
						self.sound_manager.play(sound_type, position=(self.breaking_pos[0]+0.5, self.breaking_pos[1]+0.5, self.breaking_pos[2]+0.5))
				
				# Spawn digging particles occasionally
				self.digging_particle_timer += delta_time
				if self.digging_particle_timer > 0.1: # Spawn more frequently (0.1s) for smoother feel
					self.digging_particle_timer = 0
					# Get texture of block
					block_type = self.world.block_types[self.world.get_block_number(self.breaking_pos)]
					if block_type:
						if len(block_type.tex_coords) > 2:
							tex_index = block_type.tex_coords[2][2] 
						else:
							tex_index = 0 # Fallback
						
						# Spawn on the face the crosshair is looking at, near the hit position
						if hit_pos:
							bx, by, bz = self.breaking_pos
							cx, cy, cz = bx + 0.5, by + 0.5, bz + 0.5
							dx, dy, dz = hit_pos[0] - cx, hit_pos[1] - cy, hit_pos[2] - cz
							
							# Find dominant axis to identify the Face
							adx, ady, adz = abs(dx), abs(dy), abs(dz)
							
							# Start at actual hit position
							spawn_x, spawn_y, spawn_z = hit_pos
							
							# Offset slightly from surface (normal direction) 
							# And random spread around hit point (tangent directions)
							normal_offset = 0.05
							spread = 0.2
							
							if adx > ady and adx > adz: # X Face
								sign = 1 if dx > 0 else -1
								spawn_x += sign * normal_offset
								spawn_y += (random.random() - 0.5) * spread
								spawn_z += (random.random() - 0.5) * spread
							elif ady > adx and ady > adz: # Y Face
								sign = 1 if dy > 0 else -1
								spawn_y += sign * normal_offset
								spawn_x += (random.random() - 0.5) * spread
								spawn_z += (random.random() - 0.5) * spread
							else: # Z Face
								sign = 1 if dz > 0 else -1
								spawn_z += sign * normal_offset
								spawn_x += (random.random() - 0.5) * spread
								spawn_y += (random.random() - 0.5) * spread
								
							spawn_pos = (spawn_x, spawn_y, spawn_z)
						else:
							spawn_pos = (self.breaking_pos[0]+0.5, self.breaking_pos[1]+0.5, self.breaking_pos[2]+0.5)
						
						self.particle_system.spawn(
							spawn_pos, 
							tex_index, 
							count=3, 
							speed=1.5
						)
				
				if self.breaking_progress >= self.breaking_hardness:
					# Break block
					
					# Spawn Explosion Particles
					block_type = self.world.block_types[self.world.get_block_number(self.breaking_pos)]
					if block_type:
						if len(block_type.tex_coords) > 2:
							tex_index = block_type.tex_coords[2][2]
						else:
							tex_index = 0
							
						self.particle_system.spawn(
							(self.breaking_pos[0]+0.5, self.breaking_pos[1]+0.5, self.breaking_pos[2]+0.5), 
							tex_index, 
							count=30, 
							speed=5.0, 
							is_explosion=True
						)
					
					# ADDED: Capture block ID before deleting
					block_num = self.world.get_block_number(self.breaking_pos)
					
					# Play broken sound
					if block_num:
						sound_type = self.world.block_types[block_num].sound
						self.sound_manager.play(sound_type, position=(self.breaking_pos[0]+0.5, self.breaking_pos[1]+0.5, self.breaking_pos[2]+0.5))

					self.world.set_block(self.breaking_pos, 0)
					
					# Spawn Dropped Item
					if block_num and block_num != 0:
						# Center spawn position
						spawn_pos = (self.breaking_pos[0] + 0.5, self.breaking_pos[1] + 0.5, self.breaking_pos[2] + 0.5)
						item = dropped_item.DroppedItem(self.world, spawn_pos, block_num, 1)
						self.dropped_items.append(item)

					# Transition to next block (Continuous Mining)
					self.breaking_progress = 0.0
					
					# Find what we are looking at now
					hit_result_block = None
					def next_hit_callback(current_block, next_block):
						nonlocal hit_result_block
						hit_result_block = next_block
						return True

					x, y, z = self.player.position
					y += self.player.eyelevel
					hit_ray = hit.Hit_ray(self.world, self.player.rotation, (x, y, z))
					
					while hit_ray.distance < hit.HIT_RANGE:
						if hit_ray.step(next_hit_callback):
							break
					
					if hit_result_block:
						block_num = self.world.get_block_number(hit_result_block)
						if block_num:
							block_type = self.world.block_types[block_num]
							if block_type.hardness >= 0:
								self.breaking_pos = hit_result_block
								self.breaking_hardness = block_type.hardness
								if self.breaking_hardness == 0: self.breaking_hardness = 0.05
								# Stay in breaking_block = True
							else:
								self.breaking_block = False
						else:
							self.breaking_block = False
					else:
						self.breaking_block = False
		
		# Update Particles
		self.particle_system.update(delta_time)
		
		# Update Dropped Items
		# Iterate backwards to allow removal
		for i in range(len(self.dropped_items) - 1, -1, -1):
			item = self.dropped_items[i]
			should_pickup = item.update(delta_time, self.player)
			if should_pickup:
				# Try to add to inventory
				import inventory 
				inv_item = inventory.InventoryItem(item.block_type, item.count)
				remainder = self.inventory.add_item(inv_item)
				
				if remainder < item.count:
					# Some or all picked up
					item.count = remainder
					if item.count <= 0:
						self.dropped_items.pop(i)
					# Play pop sound?
			elif item.dead:
				self.dropped_items.pop(i)
		# Sway
		target_sway_x = -self.mouse_dx * 0.02
		target_sway_y = -self.mouse_dy * 0.02
		
		# Clamp sway to avoid going off screen
		max_sway = 0.2
		target_sway_x = max(-max_sway, min(max_sway, target_sway_x))
		target_sway_y = max(-max_sway, min(max_sway, target_sway_y))
		
		# Smoothly interpolate current sway to target
		lerp_speed = 5.0
		self.hand_sway_x += (target_sway_x - self.hand_sway_x) * delta_time * lerp_speed
		self.hand_sway_y += (target_sway_y - self.hand_sway_y) * delta_time * lerp_speed
		
		# Reset accumulated mouse delta
		self.mouse_dx = 0
		self.mouse_dy = 0

		if not self.mouse_captured:
			self.player.input = [0, 0, 0]

		self.player.update(delta_time)
		
		
		# Update water flow simulation
		if self.world.water_simulator:
			self.world.water_simulator.update()
		
		# Update Mobs
		# 1. Unload mobs outside chunks to prevent falling through void
		for i in range(len(self.mobs) - 1, -1, -1):
			m = self.mobs[i]
			cpos = self.world.get_chunk_position(m.position)
			if cpos not in self.world.chunks:
				# Store data in persistent registry
				data = {
					'position': list(m.position),
					'rotation': list(m.rotation),
					'ai_state': m.ai_state,
					'type': 'pig' if isinstance(m, pig.Pig) else 'mob',
					'health': m.health
				}
				if cpos not in self.world.persistent_mobs:
					self.world.persistent_mobs[cpos] = []
				self.world.persistent_mobs[cpos].append(data)
				self.mobs.pop(i)
			else:
				# Perform standard update
				if not hasattr(m, 'player'):
					m.player = self.player
				m.update(delta_time)
				if m.dead:
					self.mobs.pop(i)

		# 2. Reload mobs from persistent registry when chunks are loaded
		for cpos in list(self.world.persistent_mobs.keys()):
			if cpos in self.world.chunks:
				for mdata in self.world.persistent_mobs[cpos]:
					if mdata.get('type') == 'pig':
						new_mob = pig.Pig(self.world, mdata['position'])
					else:
						new_mob = mob.Mob(self.world, mdata['position'])
					new_mob.rotation = mdata['rotation']
					new_mob.ai_state = mdata.get('ai_state', 'idle')
					new_mob.health = mdata.get('health', new_mob.max_health)
					self.mobs.append(new_mob)
				del self.world.persistent_mobs[cpos]

		# Update chunks (loading/unloading)
		self.world.process_chunk_updates(self.player.position)
		
		# Random block ticks (Grass spread, etc.)
		self.world.random_tick()

		# Update Listener for 3D Sound
		self.sound_manager.update_listener(self.player.position, self.player.rotation)


	def update_hand_mesh(self):
		# Generates mesh for the currently held block
		if self.holding == 0:
			self.hand_vertex_count = 0
			return

		# Check if block exists
		if self.holding >= len(self.world.block_types):
			self.hand_vertex_count = 0
			return

		block_type = self.world.block_types[self.holding]
		if not block_type:
			self.hand_vertex_count = 0
			return

		# Prepare data (interleaved)
		# x, y, z, u, v, w, shading
		data = []
		indices = []
		index_offset = 0

		if block_type.is_sprite:
			# Use ItemModel to generate 3D voxel mesh from sprite
			sprite_path = block_type.sprite_path
			if not hasattr(self, "item_model_cache"): self.item_model_cache = {}
			
			if sprite_path not in self.item_model_cache:
				self.item_model_cache[sprite_path] = item_model.ItemModel(sprite_path)
			
			gen = self.item_model_cache[sprite_path]
			vertices, tex, shades, inds = gen.generate_mesh(texture_index=block_type.sprite_index)
			
			# Interleave data
			# vertices: [v1x, v1y, v1z, v2x, ...]
			# tex: [u1, v1, w1, u2, v2, w2, ...]
			# shades: [s1, s2, ...]
			for i in range(len(vertices) // 3):
				# Pos
				data.extend(vertices[i*3 : i*3+3])
				# Tex (u,v,w)
				data.extend(tex[i*3 : i*3+3])
				# Shade
				data.append(shades[i])
			
			indices = inds
		else:
			# Iterate all faces of the model
			for i in range(len(block_type.vertex_positions)):
				face_verts = block_type.vertex_positions[i]
				face_tex = block_type.tex_coords[i]
				face_shade = block_type.shading_values[i]
				
				for j in range(4): # 4 vertices per face
					# Position
					data.extend(face_verts[j*3 : j*3+3])
					# TexCoords
					data.extend(face_tex[j*3 : j*3+3])
					# Shade
					data.append(face_shade[j])
				
				# Indices
				indices.extend([index_offset, index_offset+1, index_offset+2, index_offset, index_offset+2, index_offset+3])
				index_offset += 4

		self.hand_vertex_count = len(indices)

		# Upload to GPU
		gl.glBindVertexArray(self.hand_vao)
		
		# VBO
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.hand_vbo)
		# 7 floats per vertex * 4 bytes
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(data) * 4, (gl.GLfloat * len(data))(*data), gl.GL_STATIC_DRAW)
		
		# IBO
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.hand_ibo)
		gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, len(indices) * 4, (gl.GLuint * len(indices))(*indices), gl.GL_STATIC_DRAW)
		
		# Attributes
		stride = 7 * 4
		# 0: pos (3)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
		gl.glEnableVertexAttribArray(0)
		# 1: tex (3) - offset 12
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
		gl.glEnableVertexAttribArray(1)
		# 2: shade (1) - offset 24
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 24)
		gl.glEnableVertexAttribArray(2)
		
		# Update third person block mesh
		self.update_third_person_block_mesh()

	def update_third_person_block_mesh(self):
		if self.holding == 0 or self.holding >= len(self.world.block_types):
			self.third_person_block_vertex_count = 0
			return
		
		block_type = self.world.block_types[self.holding]
		if not block_type:
			self.third_person_block_vertex_count = 0
			return

		data = []
		indices = []
		index_offset = 0

		if block_type.is_sprite:
			sprite_path = block_type.sprite_path
			if not hasattr(self, "item_model_cache"): self.item_model_cache = {}
			if sprite_path not in self.item_model_cache:
				self.item_model_cache[sprite_path] = item_model.ItemModel(sprite_path)
			
			gen = self.item_model_cache[sprite_path]
			vertices, tex, shades, inds = gen.generate_mesh(texture_index=block_type.sprite_index)
			
			for i in range(len(vertices) // 3):
				data.extend(vertices[i*3 : i*3+3])
				data.extend(tex[i*3 : i*3+3])
				data.append(shades[i])
			indices = inds
		else:
			for i in range(len(block_type.vertex_positions)):
				face_verts = block_type.vertex_positions[i]
				face_tex = block_type.tex_coords[i]
				face_shade = block_type.shading_values[i]
				for j in range(4):
					data.extend(face_verts[j*3 : j*3+3])
					data.extend(face_tex[j*3 : j*3+3])
					data.append(face_shade[j])
				indices.extend([index_offset, index_offset+1, index_offset+2, index_offset, index_offset+2, index_offset+3])
				index_offset += 4

		self.third_person_block_vertex_count = len(indices)
		
		gl.glBindVertexArray(self.third_person_block_vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.third_person_block_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(data) * 4, (gl.GLfloat * len(data))(*data), gl.GL_STATIC_DRAW)
		
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.third_person_block_ibo)
		gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, len(indices) * 4, (gl.GLuint * len(indices))(*indices), gl.GL_STATIC_DRAW)
		
		stride = 7 * 4
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
		gl.glEnableVertexAttribArray(0)
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
		gl.glEnableVertexAttribArray(1)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 24)
		gl.glEnableVertexAttribArray(2)

	def draw_third_person_block(self):
		if self.third_person_block_vertex_count == 0 or self.player.camera_mode == 0:
			return
			
		# Steve's World Matrix
		m_mob = matrix.Matrix()
		m_mob.load_identity()
		m_mob.translate(*self.steve.position)
		m_mob.rotate_2d(-self.steve.rotation[0] - math.pi, 0)
		
		# Hand Offset Matrix
		ps = 0.06
		m_arm = matrix.Matrix()
		m_arm.load_identity()
		m_arm.translate(6*ps, 24*ps, 0) # Pivot at shoulder
		m_arm.rotate(self.steve.r_arm.rotation[0], 1, 0, 0) # Rotate Arm
		
		# Apply custom transform if exists
		sid = str(self.holding)
		s = self.item_transforms.get(sid, {}).get("TPS", {"pos": [3*ps, -11*ps, 0.15], "rot": [0, 45, 0], "scale": [0.25, 0.25, 0.25]})
		
		m_arm.translate(*s["pos"]) 
		m_arm.rotate(math.radians(s["rot"][0]), 1, 0, 0)
		m_arm.rotate(math.radians(s["rot"][1]), 0, 1, 0)
		m_arm.rotate(math.radians(s["rot"][2]), 0, 0, 1)
		m_arm.scale(*s["scale"]) 
		m_arm.translate(-0.5, -0.5, -0.5) 
		
		m_final = m_mob * m_arm
		
		# IMPORTANT: Re-bind world texture array (Mob.draw binds a single 2D texture)
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
		
		# Draw with world shader
		self.shader.use()
		mvp = self.player.p_matrix * self.player.mv_matrix * m_final
		self.shader.uniform_matrix(self.player.shader_matrix_location, mvp)
		
		gl.glBindVertexArray(self.third_person_block_vao)
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.third_person_block_ibo)
		gl.glDrawElements(gl.GL_TRIANGLES, self.third_person_block_vertex_count, gl.GL_UNSIGNED_INT, None)

	def draw_hand(self):
		# Draw empty arm if nothing held
		if self.holding == 0 or self.hand_vertex_count == 0:
			self.draw_empty_hand()
			return

		# Position the hand relative to camera
		# Use Identity View Matrix (Camera at 0,0,0 looking -Z)
		# We need to construct a transformation that places the block on screen
		
		hand_mv = matrix.Matrix()
		hand_mv.load_identity()
		
		# Calculate Bobbing Offsets
		bob_x = math.sin(self.hand_bob_timer) * 0.02
		bob_y = math.sin(self.hand_bob_timer * 2.0) * 0.02
		
		# Aspect ratio adjustment
		aspect = self.width / self.height
		# Standard aspect is ~1.33 or ~1.77.
		# If aspect is large (wide), we want hand further right.
		# But '0.6' in NDC is relative to height in some projections, or relative to width?
		# In typical Perspective with FOV Y fixed:
		# X range is [-aspect, aspect] * scale.
		# So 0.6 might be closer to center on wide screen.
		# Let's fix it relative to aspect.
		
		base_x = 0.6 * (aspect / 1.77) # Normalize to 16:9
		if base_x < 0.6: base_x = 0.6 # Don't go too intrusive on square screens
		
		# Position: slightly right, down, and forward + Animation Offsets
		sid = str(self.holding)
		s = self.item_transforms.get(sid, {}).get("FPS", {"pos": [base_x, -0.6, -1.2], "rot": [0, -45, 0], "scale": [0.6, 0.6, 0.6]})
		
		# Debug print every 60 frames
		if self.holding != 0 and random.random() < 0.01:
			print(f"Draw Hand ID {sid}: Pos {s['pos']}")
		
		hand_mv.translate(s["pos"][0] + self.hand_sway_x + bob_x, s["pos"][1] + self.hand_sway_y + bob_y, s["pos"][2])
		
		# Apply Rotation
		hand_mv.rotate(math.radians(s["rot"][0]), 1, 0, 0)
		hand_mv.rotate(math.radians(s["rot"][1]), 0, 1, 0)
		hand_mv.rotate(math.radians(s["rot"][2]), 0, 0, 1)
		
		# Apply Punchy Swing Animation (Translation + Rotation)
		swing = math.sin(self.hand_swing)
		
		# Move forward (Z+) and slightly inward (X-)
		offset_z = swing * 0.2
		offset_x = -swing * 0.1
		offset_y = swing * 0.1
		hand_mv.translate(offset_x, offset_y, offset_z)
		
		hand_mv.rotate(swing * 0.3, 1, 0, 0) # Pitch
		hand_mv.rotate(swing * 0.1, 0, 1, 0) # Yaw
		
		# Scale
		hand_mv.scale(*s["scale"])
		hand_mv.translate(-0.5, -0.5, -0.5) # Center if needed (usually ItemModel is centered, but blocks are 0..1)
		# Actually ItemModel.generate_mesh CENTERS the model at 0,0,0. 
		# But standard blocks are 0..1? 
		# Let's check block_type. vertex_positions[0][0..2] is usually 1, 0, 0 etc.
		# If it's a cube from 0 to 1, we should translate by -0.5.
		# If it's ItemModel, it's already centered.
		
		block_type = self.world.block_types[self.holding]
		if not block_type.is_sprite:
			# Cubes need centring
			# hand_mv.translate(-0.5, -0.5, -0.5) # Already done above? 
			pass
		else:
			# Sprites are already centered by ItemModel
			pass

		# Combine with projection matrix
		# Note: self.player.p_matrix is set based on FOV/Aspect ratio
		mvp = self.player.p_matrix * hand_mv
		
		self.shader.use()
		self.shader.uniform_matrix(self.player.shader_matrix_location, mvp)
		
		# Disable Depth Test so it draws on top? 
		# Usually hand draws on top. Or just clear depth?
		# But clearing depth might mess up other things if we drew transparents.
		# For now, let's just clear depth buffer before drawing hand
		gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
		
		gl.glBindVertexArray(self.hand_vao)
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.hand_ibo)
		gl.glDrawElements(gl.GL_TRIANGLES, self.hand_vertex_count, gl.GL_UNSIGNED_INT, None)

	def init_empty_hand_mesh(self):
		# Load Steve texture for the arm
		try:
			img = pyglet.image.load("textures/steve.png")
			self.empty_hand_texture = img.get_texture()
			gl.glBindTexture(gl.GL_TEXTURE_2D, self.empty_hand_texture.id)
			gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
			gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
		except:
			self.empty_hand_texture = None
			return
		
		# Build a simple arm box mesh (right arm from Steve texture)
		# UV coords for right arm: u=40, v=16, size 4x12x4
		ps = 0.15  # Pixel scale for first person
		w, h, d = 4*ps, 12*ps, 4*ps
		
		# Box vertices (centered on X/Z, Y from 0 to h - FLIPPED so hand at end)
		x1, x2 = -w/2, w/2
		y1, y2 = 0, h  # y1=shoulder(origin), y2=hand(extending)
		z1, z2 = -d/2, d/2
		
		def uv(u, v): return (u/64.0, 1.0 - v/64.0)
		
		verts = []
		# Front face (Z+) - y1=Shoulder (v20), y2=Hand (v32)
		verts.extend([x1, y1, z2, *uv(44, 20), 0.8])
		verts.extend([x2, y1, z2, *uv(48, 20), 0.8])
		verts.extend([x2, y2, z2, *uv(48, 32), 0.8])
		verts.extend([x1, y2, z2, *uv(44, 32), 0.8])
		# Back face (Z-)
		verts.extend([x2, y1, z1, *uv(52, 20), 0.8])
		verts.extend([x1, y1, z1, *uv(56, 20), 0.8])
		verts.extend([x1, y2, z1, *uv(56, 32), 0.8])
		verts.extend([x2, y2, z1, *uv(52, 32), 0.8])
		# Right face (X+)
		verts.extend([x2, y1, z2, *uv(40, 20), 0.6])
		verts.extend([x2, y1, z1, *uv(44, 20), 0.6])
		verts.extend([x2, y2, z1, *uv(44, 32), 0.6])
		verts.extend([x2, y2, z2, *uv(40, 32), 0.6])
		# Left face (X-)
		verts.extend([x1, y1, z1, *uv(48, 20), 0.6])
		verts.extend([x1, y1, z2, *uv(52, 20), 0.6])
		verts.extend([x1, y2, z2, *uv(52, 32), 0.6])
		verts.extend([x1, y2, z1, *uv(48, 32), 0.6])
		
		# Hand Tip (y2) - Top of Cylinder in Local Space (Normal +Y)
		# Winding: x1z2 -> x2z2 -> x2z1 -> x1z1
		# Texture: Bottom of Arm (48,16 to 52,20)
		# Mapping: x1z2 -> 48,20. x2z2 -> 52,20. x2z1 -> 52,16. x1z1 -> 48,16.
		verts.extend([x1, y2, z2, *uv(48, 20), 0.5])
		verts.extend([x2, y2, z2, *uv(52, 20), 0.5])
		verts.extend([x2, y2, z1, *uv(52, 16), 0.5])
		verts.extend([x1, y2, z1, *uv(48, 16), 0.5])
		
		# Shoulder (y1) - Bottom of Cylinder in Local Space (Normal -Y)
		# Winding: x1z1 -> x2z1 -> x2z2 -> x1z2
		# Texture: Top of Arm (44,16 to 48,20)
		# Mapping: x1z1 -> 44,16. x2z1 -> 48,16. x2z2 -> 48,20. x1z2 -> 44,20.
		verts.extend([x1, y1, z1, *uv(44, 16), 0.5])
		verts.extend([x2, y1, z1, *uv(48, 16), 0.5])
		verts.extend([x2, y1, z2, *uv(48, 20), 0.5])
		verts.extend([x1, y1, z2, *uv(44, 20), 0.5])
		
		self.empty_hand_vertex_count = 24  # 6 faces * 4 verts
		
		gl.glBindVertexArray(self.empty_hand_vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.empty_hand_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(verts)*4, (gl.GLfloat * len(verts))(*verts), gl.GL_STATIC_DRAW)
		
		stride = 6 * 4  # x,y,z, u,v, shade
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
		gl.glEnableVertexAttribArray(0)
		gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
		gl.glEnableVertexAttribArray(1)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 20)
		gl.glEnableVertexAttribArray(2)

	def draw_empty_hand(self):
		if self.empty_hand_vertex_count == 0 or not self.empty_hand_texture:
			return
		
		hand_mv = matrix.Matrix()
		hand_mv.load_identity()
		
		# Calculate Bobbing Offsets
		bob_x = math.sin(self.hand_bob_timer) * 0.02
		bob_y = math.sin(self.hand_bob_timer * 2.0) * 0.02
		
		aspect = self.width / self.height
		base_x = 0.6 * (aspect / 1.77)
		if base_x < 0.5: base_x = 0.5
		
		# Minecraft-style arm: positioned bottom-right, pointing forward towards crosshair
		hand_mv.translate(base_x + self.hand_sway_x + bob_x, -0.55 + self.hand_sway_y + bob_y, -0.2)
		
		# Arm points forward (towards -Z / crosshair)
		# User specified rotation values
		# Order changed: Y (Yaw) then X (Pitch) to pan correctly
		hand_mv.rotate(math.radians(10), 0, 1, 0)   # Y rotation (Yaw)
		hand_mv.rotate(math.radians(-68), 1, 0, 0)  # X rotation (Pitch)
		
		# Apply Punchy Swing Animation
		swing = math.sin(self.hand_swing)
		
		# Move arm forward and inward during swing
		offset_z = swing * 0.15
		offset_x = -swing * 0.1
		hand_mv.translate(offset_x, 0, offset_z)
		
		# Rotate relative to arm's local orientation
		hand_mv.rotate(swing * 0.4, 0, 1, 0) # Swing towards center
		hand_mv.rotate(swing * 0.2, 1, 0, 0) # Pitch
		
		# Scale down
		hand_mv.scale(0.4, 0.4, 0.4)
		
		mvp = self.player.p_matrix * hand_mv
		
		# Use mob shader for arm (it uses 2D texture)
		self.steve.shader.use()
		
		flat_mvp = []
		for i in range(4):
			for j in range(4):
				flat_mvp.append(mvp.data[i][j])
		gl.glUniformMatrix4fv(self.steve.matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_mvp))
		
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D, self.empty_hand_texture.id)
		gl.glUniform1i(self.steve.tex_loc, 0)
		gl.glUniform1f(self.steve.hurt_loc, 0.0)
		
		gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
		gl.glDisable(gl.GL_CULL_FACE)
		
		gl.glBindVertexArray(self.empty_hand_vao)
		gl.glDrawArrays(gl.GL_QUADS, 0, self.empty_hand_vertex_count)
		
		gl.glEnable(gl.GL_CULL_FACE)
		self.shader.use()

	# input functions

	def on_resize(self, width, height):
		print(f"Resize {width} * {height}")
		gl.glViewport(0, 0, width, height)
		
		if hasattr(self, 'gui'):
			self.gui.on_resize(width, height)

		self.player.view_width = width
		self.player.view_height = height
		
		# Update water flow simulation
		pass

	def on_mouse_press(self, x, y, button, modifiers):
		if self.gui.menu_open:
			# Pass input to GUI logic
			self.gui.on_mouse_press(x, y, button, modifiers)
			return

		if not self.mouse_captured:
			self.mouse_captured = True
			self.set_exclusive_mouse(True)
			return

		def hit_callback(current_block, next_block):
			if button == pyglet.window.mouse.RIGHT: 
				# INTERACTION CHECK (Functional Blocks)
				block_id = self.world.get_block_number(next_block)
				if block_id == 58: # Crafting Table
					self.inventory.crafting_size = 3
					self.gui.menu_open = True
					self.mouse_captured = False
					self.set_exclusive_mouse(False)
					return True # Consume event
				
				# Trigger swing animation
				self.is_swinging = True
				if not self.breaking_block:
					self.hand_swing = 0.0
				
				# Collision check before placing block
				# Create a collider for the block we want to place
				block_pos = current_block
				# Standard block collider (0,0,0) to (1,1,1) offset by block_pos
				block_col = collider.Collider(block_pos, (block_pos[0]+1, block_pos[1]+1, block_pos[2]+1))
				
				# Check if it intersects with player
				# Check Inventory first
				if self.holding == 0:
					return
				
				# Get item to confirm we have it
				held_item = self.inventory.get_selected_item()
				if not held_item or held_item.count <= 0:
					return

				# Check Collision
				# Use a much smaller collider for placement to make "towering" (placing blocks under yourself) easier
				# Shaving 0.4 from bottom to be extremely forgiving for jumps
				placement_collider = collider.Collider(
					(self.player.collider.x1 + 0.1, self.player.collider.y1 + 0.4, self.player.collider.z1 + 0.1),
					(self.player.collider.x2 - 0.1, self.player.collider.y2 - 0.1, self.player.collider.z2 - 0.1)
				)
				
				if placement_collider & block_col:
					return 
				
				self.world.set_block(current_block, self.holding)
				
				# Play placement sound
				sound_type = self.world.block_types[self.holding].sound
				self.sound_manager.play(sound_type, position=(current_block[0]+0.5, current_block[1]+0.5, current_block[2]+0.5))
				
				# Consume item
				self.inventory.consume_held_item(1)
				
				# Update holding state if ran out
				new_held = self.inventory.get_selected_block()
				if new_held:
					self.holding = new_held
				else:
					self.holding = 0
					self.hand_vertex_count = 0
				self.update_hand_mesh()
				
			elif button == pyglet.window.mouse.LEFT:
				# Trigger swing animation
				self.is_swinging = True
				if not self.breaking_block:
					self.hand_swing = 0.0

				# Attack Mobs
				# Raycast against mobs first (higher priority than blocks usually? Or range dependent)
				# Simple Mob Raycast
				hit_mob = None
				hit_dist = 4.0 # Attack Range
				
				# Iterate all active mobs
				for m in self.mobs:
					dx = m.position[0] - self.player.position[0]
					dy = m.position[1] - self.player.position[1] # Feet diff
					dz = m.position[2] - self.player.position[2]
					
					dist = math.sqrt(dx*dx + dy*dy + dz*dz)
					if dist > hit_dist + 2.0: continue # broad phase
					
					# Bounding Box check
					# Mob width=0.6, height=1.8
					# Check intersection with look vector
					
					# Using simple sphere check for now or AABB logic?
					# AABB logic via collider?
					# Mob inherits from Entity, has self.collider
					# Player look vector:
					
					# Ray Origin: Player hit_ray origin
					# Ray Dir: Player hit_ray vector
					
					# Easier: Check if line segment intersects AABB
					# Or simpler: Is mob "looked at"?
					# Dot product of look vector and direction to mob?
					
					# Direction to mob center (approx)
					to_mob = [
						m.position[0] - self.player.position[0],
						(m.position[1] + m.height/2) - (self.player.position[1] + self.player.eyelevel),
						m.position[2] - self.player.position[2]
					]
					dist_to_center = math.sqrt(to_mob[0]**2 + to_mob[1]**2 + to_mob[2]**2)
					if dist_to_center > hit_dist: continue

					to_mob_norm = [c / dist_to_center for c in to_mob]
					
					# Dot product with look vector
					# view vector from hit_ray
					look = hit_ray.vector
					dot = look[0]*to_mob_norm[0] + look[1]*to_mob_norm[1] + look[2]*to_mob_norm[2]
					
					# If looking mostly at mob (threshold depends on distance/size)
					# For a 1m wide mob at 3m, angle is roughly atan(0.5/3) ~ 10 degrees.
					# Cos(10) ~ 0.98.
					# Let's be generous: 0.95
					if dot > 0.9 + (0.05 / max(1.0, dist_to_center)): # Closer = easier to hit?
						# Hit!
						if not hit_mob or dist_to_center < hit_dist:
							hit_mob = m
							hit_dist = dist_to_center
				
				if hit_mob:
					# Deal Damage
					damage = 4 # Fist damage? or Tool damage
					hit_mob.take_damage(damage)
					if hasattr(hit_mob, 'on_hit'):
						hit_mob.on_hit(self.player)
					print(f"Mob Hit! Health: {hit_mob.health}")
					
					# Knockback
					kb_strength = 0.5
					# Repel from player
					kb_x = hit_mob.position[0] - self.player.position[0]
					kb_z = hit_mob.position[2] - self.player.position[2]
					length = math.sqrt(kb_x*kb_x + kb_z*kb_z)
					if length > 0.01:
						hit_mob.velocity[0] += (kb_x/length) * 10.0 * kb_strength
						hit_mob.velocity[2] += (kb_z/length) * 10.0 * kb_strength
						
					hit_mob.velocity[1] += 4.0 * kb_strength # Lift
					
					# Remove if dead (handled in Mob.update, but we can play sound/particle here)
					if hit_mob.dead:
						print("Mob Killed!")
						# self.mobs.remove(hit_mob) # Let update loop handle removal or do it here?
						# Update loop might try to update a removed mob if iterating?
						# Entity update handles logic, Main loop removal is safe if done carefully.
						# We rely on main loop removing dead mobs? 
						# Currently main loop doesn't check dead. Let's add that to main update.
					
					return # Hit mob, don't break block behind it?
				
				
				# Start Breaking
				
				# self.world.set_block(next_block, 0) # OLD INSTANT BREAK
				
				# Get block info
				x, y, z = next_block
				block_num = self.world.get_block_number(next_block)
				if block_num:
					block_type = self.world.block_types[block_num]
					if block_type.hardness >= 0: # Check if breakable
						self.breaking_block = True
						self.breaking_pos = next_block
						self.breaking_progress = 0.0
						self.breaking_hardness = block_type.hardness
						if self.breaking_hardness == 0: self.breaking_hardness = 0.05 # Prevent div by 0 and allow instant
			
			elif button == pyglet.window.mouse.MIDDLE: 
				self.holding = self.world.get_block_number(next_block)
				self.update_hand_mesh()

		x, y, z = self.player.position
		y += self.player.eyelevel

		hit_ray = hit.Hit_ray(self.world, self.player.rotation, (x, y, z))

		while hit_ray.distance < hit.HIT_RANGE:
			if hit_ray.step(hit_callback):
				break

	def on_mouse_release(self, x, y, button, modifiers):
		if button == pyglet.window.mouse.LEFT:
			self.breaking_block = False
			self.breaking_progress = 0.0
			self.breaking_pos = None
			self.hand_swing = 0.0

	def check_hot_reload(self, dt):
		if os.path.exists("data/item_transforms.json"):
			try:
				mtime = os.path.getmtime("data/item_transforms.json")
				if mtime > self.last_transforms_mtime:
					self.last_transforms_mtime = mtime
					with open("data/item_transforms.json", "r") as f:
						self.item_transforms = json.load(f)
					print("Hot Reload: Item transforms updated.")
			except: pass

	def on_mouse_motion(self, x, y, delta_x, delta_y):
		# Always update GUI mouse pos
		self.gui.on_mouse_motion(x, y, delta_x, delta_y)

		if self.mouse_captured:
			sensitivity = 0.004

			self.player.rotation[0] += delta_x * sensitivity
			self.player.rotation[1] += delta_y * sensitivity

			self.player.rotation[1] = max(-math.tau / 4, min(math.tau / 4, self.player.rotation[1]))
			
			self.mouse_dx += delta_x
			self.mouse_dy += delta_y

	def on_mouse_drag(self, x, y, delta_x, delta_y, buttons, modifiers):
		self.on_mouse_motion(x, y, delta_x, delta_y)




	def on_key_press(self, key, modifiers):
		# --- Global Controls (Always Active) ---
		
		# Camera Toggle (F5)
		if key == pyglet.window.key.F5:
			self.player.camera_mode = (self.player.camera_mode + 1) % 3
			print(f"Camera Mode: {self.player.camera_mode}")
			return

		# Reload Item Transforms (F10)
		if key == pyglet.window.key.F10:
			if os.path.exists("data/item_transforms.json"):
				try:
					with open("data/item_transforms.json", "r") as f:
						self.item_transforms = json.load(f)
					print("Item transforms reloaded!")
				except Exception as e:
					print(f"Failed to reload transforms: {e}")
			return

		# Inventory Toggle
		if key == pyglet.window.key.E:
			self.inventory.crafting_size = 2 # Always personal for E
			self.gui.menu_open = not self.gui.menu_open
			if self.gui.menu_open:
				self.mouse_captured = False
				self.set_exclusive_mouse(False)
			else:
				self.mouse_captured = True
				self.set_exclusive_mouse(True)
			return

		# Escape / Menu
		elif key == pyglet.window.key.ESCAPE:
			if self.gui.menu_open:
				self.gui.menu_open = False
				self.mouse_captured = True
				self.set_exclusive_mouse(True)
			else:
				self.mouse_captured = False
				self.set_exclusive_mouse(False)
				# Save on pause (ESC)
				self.auto_save(0)
			return

		# Hotbar Selection (1-9)
		# Handle both top row (49-57) and Numpad (if needed, but standard is top row)
		# 49 is '1' in ASCII/Key code
		elif 49 <= key <= 57:
			index = key - 49
			self.inventory.select_slot(index)
			
			# Update held block immediately
			block = self.inventory.get_selected_block()
			if block:
				self.holding = block
				self.update_hand_mesh()
			else:
				self.holding = 0 # Empty hand
				self.hand_vertex_count = 0
			return

		# Drop Item (Q)
		elif key == pyglet.window.key.Q:
			# Get current item
			item = self.inventory.get_selected_item()
			if item:
				count_to_drop = 0
				
				# Check modifier for Stack Drop (Ctrl + Q)
				if modifiers & pyglet.window.key.MOD_CTRL:
					count_to_drop = item.count
				else:
					count_to_drop = 1
				
				# Get block info before consuming
				block_type = item.block_type
				
				# Consume from inventory
				if self.inventory.consume_held_item(count_to_drop):
					# Calculate drop position and velocity
					x, y, z = self.player.position
					y += self.player.eyelevel - 0.2 # Eye level
					
					# Direction vector from rotation
					# Player.py: rotation[0] is Yaw, rotation[1] is Pitch
					rot_yaw = self.player.rotation[0]
					rot_pitch = self.player.rotation[1]
					
					# Direction
					# Movement uses: acc_x = cos(yaw), acc_z = sin(yaw)
					# Pitch: Mouse Up decreases pitch (-90 is up). 
					# So Up Vector component should be positive when pitch is negative. -> -sin(pitch)
					
					speed = 6.0 
					
					# X and Z (Horizontal) affected by cos(pitch) (length of projection)
					h_scale = math.cos(rot_pitch)
					
					vx = math.cos(rot_yaw) * h_scale * speed
					vz = math.sin(rot_yaw) * h_scale * speed
					vy = -math.sin(rot_pitch) * speed + 1.5 # Add little up throw
					
					# Less Random spread
					vx += random.uniform(-0.5, 0.5)
					vz += random.uniform(-0.5, 0.5)

					# Spawn Item
					dropped = dropped_item.DroppedItem(self.world, (x, y, z), block_type, count_to_drop, velocity=(vx, vy, vz))
					# Add drag so it doesn't fly forever
					# (Drag logic handled in DroppedItem update usually?) 
					# DroppedItem update has linear damping "friction" on ground, maybe add air drag?
					# DroppedItem implementation just added `velocity` init support.
					self.dropped_items.append(dropped)
					
					# Update Hand
					new_held = self.inventory.get_selected_block()
					if new_held:
						self.holding = new_held
					else:
						self.holding = 0
						self.hand_vertex_count = 0
					self.update_hand_mesh()
			return

		# --- Gameplay Controls (Only when mouse captured) ---
		if not self.mouse_captured:
			return

		if key == pyglet.window.key.D:
			self.player.input[0] += 1
		elif key == pyglet.window.key.A:
			self.player.input[0] -= 1
		elif key == pyglet.window.key.W:
			self.player.input[2] += 1
		elif key == pyglet.window.key.S:
			self.player.input[2] -= 1

		elif key == pyglet.window.key.SPACE:
			self.player.input[1] += 1
		elif key == pyglet.window.key.LSHIFT:
			self.player.crouching = True
		elif key == pyglet.window.key.LCTRL:
			self.player.sprinting = True

		elif key == pyglet.window.key.TAB:
			self.player.flying = not self.player.flying
			
		# Old number keys block removed from here
		
		# Teleport (R) - Optional debug
		elif key == pyglet.window.key.R:
			# ... existing teleport info logic if needed, or remove ...
			pass

		elif key == pyglet.window.key.O:
			self.auto_save(0)

		elif key == pyglet.window.key.R:
			# how large is the world?

			max_y = 0

			max_x, max_z = (0, 0)
			min_x, min_z = (0, 0)

			for pos in self.world.chunks:
				x, y, z = pos

				max_y = max(max_y, (y + 1) * chunk.CHUNK_HEIGHT)

				max_x = max(max_x, (x + 1) * chunk.CHUNK_WIDTH)
				min_x = min(min_x, x * chunk.CHUNK_WIDTH)

				max_z = max(max_z, (z + 1) * chunk.CHUNK_LENGTH)
				min_z = min(min_z, z * chunk.CHUNK_LENGTH)

			# get random X & Z coordinates to teleport the player to

			x = random.randint(min_x, max_x)
			z = random.randint(min_z, max_z)

			# find height at which to teleport to, by finding the first non-air block from the top of the world

			for y in range(chunk.CHUNK_HEIGHT - 1, -1, -1):
				if not self.world.get_block_number((x, y, z)):
					continue

				self.player.teleport((x, y + 1, z))
				break


		elif key == pyglet.window.key.ESCAPE:
			if self.gui.menu_open:
				self.gui.menu_open = False
				self.mouse_captured = True
				self.set_exclusive_mouse(True)
			else:
				self.mouse_captured = False
				self.set_exclusive_mouse(False)
				# Save on pause (ESC)
				self.auto_save(0)
		
		# Inventory Controls
		elif key == pyglet.window.key.E:
			self.gui.menu_open = not self.gui.menu_open
			if self.gui.menu_open:
				self.mouse_captured = False
				self.set_exclusive_mouse(False)
			else:
				self.mouse_captured = True
				self.set_exclusive_mouse(True)
		
		# Hotbar Selection (1-9)
		# 49 is '1', 57 is '9'
		elif 49 <= key <= 57:
			index = key - 49
			

			self.inventory.select_slot(index)
			
			# Update held block
			block = self.inventory.get_selected_block()
			if block:
				self.holding = block
				self.update_hand_mesh()
				print(f"Selected Slot {index+1}: Holding Item ID {self.holding}")
			else:
				self.holding = 0 # Empty hand
				self.hand_vertex_count = 0
				print(f"Selected Slot {index+1}: Empty Hand")

		# Trigger Mob Animation (K)
		elif key == pyglet.window.key.K:
			for m in self.mobs:
				# Toggle or Set? Request says "start" (başlatalım). So set to walk.
				# If we want toggle: if m.animation_state == 'walk': m.animation_state = None else ...
				# Previous logic was just set. Sticking to set.
				m.animation_state = 'walk'

		# Spawn Mob (L)
		elif key == pyglet.window.key.L:
			x, y, z = self.player.position
			spawn_pos = (x, y + 3, z)
			new_mob = mob.Mob(self.world, spawn_pos)
			self.mobs.append(new_mob)
			print(f"Spawned Mob at {spawn_pos}")

		# Spawn Pig (P)
		elif key == pyglet.window.key.P:
			x, y, z = self.player.position
			spawn_pos = (x, y + 3, z)
			new_pig = pig.Pig(self.world, spawn_pos)
			self.mobs.append(new_pig)
			print(f"Spawned Pig at {spawn_pos}")

		# Test Pig Animation (I)
		elif key == pyglet.window.key.I:
			for m in self.mobs:
				if isinstance(m, pig.Pig):
					m.trigger_test_animation()
			print("Triggered Pig Animation Sequence")
	
	def draw_reticle(self):
		"""Draw a simple crosshair at the center of the screen"""
		# Calculate NDC size
		size = 10
		ndc_w = size / self.width * 2
		ndc_h = size / self.height * 2
		
		# Vertices (4 points, 2 lines)
		verts = [
			-ndc_w, 0.0,
			 ndc_w, 0.0,
			 0.0, -ndc_h,
			 0.0,  ndc_h
		]
		
		c_verts = (gl.GLfloat * len(verts))(*verts)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.crosshair_vbo)
		gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, len(verts)*4, c_verts)
		
		self.overlay_shader.use()
		gl.glUniform4f(self.overlay_color_loc, 1.0, 1.0, 1.0, 1.0) # White
		
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glBindVertexArray(self.crosshair_vao)
		gl.glDrawArrays(gl.GL_LINES, 0, 4)
		gl.glEnable(gl.GL_DEPTH_TEST)


	def on_draw(self):
		self.player.update_matrices()
		
		# Frustum Culling Update
		# Changed to simpler CamPos + Rotation logic for reliability
		self.world.frustum.update(self.player.position, self.player.rotation)
		
		# Calculate submersion once
		submersion = self.player.submersion_factor

		# bind textures
		gl.glActiveTexture(gl.GL_TEXTURE0)
		# Ensure we utilize the correct target for texture arrays
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
		gl.glUniform1i(self.shader_sampler_location, 0)

		# draw stuff
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		
		# Dynamic Clear Color based on submersion
		if submersion > 0:
			# Lerp between Sky Color (0.5, 0.69, 1.0) and Water Color (0.1, 0.2, 0.5)
			# But if we want simple tinting, just Lerp
			# Let's say max underwater effect is at submersion=1.0
			
			sky_r, sky_g, sky_b = 0.5, 0.69, 1.0
			water_r, water_g, water_b = 0.1, 0.2, 0.5
			
			r = sky_r * (1.0 - submersion) + water_r * submersion
			g = sky_g * (1.0 - submersion) + water_g * submersion
			b = sky_b * (1.0 - submersion) + water_b * submersion
			
			gl.glClearColor(r, g, b, 1.0)
		else:
			gl.glClearColor(0.5, 0.69, 1.0, 1.0)
			
		gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

		self.shader.uniform1f(self.shader_alpha_factor_location, 1.0)
		self.world.draw('solid')
		
		# Draw water blocks with transparency
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		self.shader.uniform1f(self.shader_alpha_factor_location, 0.65) # 0.65 is a good "lightly transparent" value
		
		# Optional: Water usually doesn't need to cull backfaces if transparent, 
		# but for performance and to avoid visual noise from overlapping water faces, we can keep it.
		# However, seeing the "other side" of the water volume is often better.
		gl.glDisable(gl.GL_CULL_FACE) 
		self.world.draw('water')
		gl.glEnable(gl.GL_CULL_FACE)
		
		gl.glDisable(gl.GL_BLEND)
		self.shader.uniform1f(self.shader_alpha_factor_location, 1.0)
		
		# Draw Particles
		self.particle_system.draw(self.player)

		# Draw Mobs
		for m in self.mobs:
			# Frustum Cull Mobs
			# Approx Mob Size: 0.6x1.8x0.6
			pad = 0.5
			if self.world.frustum.is_box_visible(
				m.position[0] - pad, m.position[1], m.position[2] - pad,
				m.position[0] + pad, m.position[1] + 2.0, m.position[2] + pad
			):
				m.draw(self.player.p_matrix, self.player.mv_matrix)
			
		# Draw Player Model (Steve) in 3rd Person
		if self.player.camera_mode != 0:
			gl.glDisable(gl.GL_CULL_FACE)
			self.steve.draw(self.player.p_matrix, self.player.mv_matrix)
			gl.glEnable(gl.GL_CULL_FACE)
			
			# Draw held block in hand
			self.draw_third_person_block()

		# Draw Dropped Items
		if self.dropped_items:

			self.gui.icon_shader.use()
			
			# Calculate VP Matrix (Projection * View)
			vp_matrix = self.player.p_matrix * self.player.mv_matrix
			
			# Flat list for uniform
			flat_vp = []
			for i in range(4):
				for j in range(4):
					flat_vp.append(vp_matrix.data[i][j])
			
			gl.glUniformMatrix4fv(self.gui.icon_proj_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_vp))
			gl.glUniform1i(self.gui.icon_tex_loc, 0)
			
			gl.glActiveTexture(gl.GL_TEXTURE0)
			gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
			
			gl.glEnable(gl.GL_DEPTH_TEST)
			# gl.glDisable(gl.GL_CULL_FACE) # Ensure double sided rendering just in case
			
			for item in self.dropped_items:
				# Frustum Cull Items
				# Approx Size 0.5
				if self.world.frustum.is_box_visible(
					item.position[0] - 0.5, item.position[1] - 0.5, item.position[2] - 0.5,
					item.position[0] + 0.5, item.position[1] + 0.5, item.position[2] + 0.5
				):
					# Set Model Matrix
					m = item.get_model_matrix()
					flat_model = []
					for i in range(4):
						for j in range(4):
							flat_model.append(m.data[i][j])
							
					gl.glUniformMatrix4fv(self.gui.icon_model_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_model))
					
					# Draw Item
					gl.glBindVertexArray(item.vao)
					gl.glDrawArrays(gl.GL_TRIANGLES, 0, item.vertex_count)
				
			gl.glBindVertexArray(0)
			self.shader.use()
		
		# Underwater Filter Overlay
		if submersion > 0:
			self.overlay_shader.use()
			
			# Modulate alpha by submersion factor
			# Max alpha = 0.5
			alpha = 0.5 * submersion
			gl.glUniform4f(self.overlay_color_loc, 0.0, 0.1, 0.8, alpha)
			
			gl.glEnable(gl.GL_BLEND)
			gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
			gl.glDisable(gl.GL_DEPTH_TEST)
			
			gl.glBindVertexArray(self.overlay_vao)
			gl.glDrawArrays(gl.GL_TRIANGLE_FAN, 0, 4)
			
			gl.glDisable(gl.GL_BLEND)
			gl.glEnable(gl.GL_DEPTH_TEST)
			
			self.shader.use() # Restore main shader

		# Draw Breaking Overlay
		if self.breaking_block and self.breaking_progress > 0:
			self.draw_breaking_overlay()

		# Draw GUI (Inventory, Hotbar)
		self.gui.draw()

		# Draw Reticle (Crosshair) - Only if menu closed
		if not self.gui.menu_open:
			self.draw_reticle()
		
		# Draw Hand - Only if menu closed AND first-person mode
		if not self.gui.menu_open and self.player.camera_mode == 0:
			self.draw_hand()
		
		self.shader.use()

		gl.glFinish()

	def draw_breaking_overlay(self):
		if not self.breaking_pos:
			return
			
		# Calculate stage (0-9)
		ratio = self.breaking_progress / self.breaking_hardness if self.breaking_hardness > 0 else 0
		stage = int(ratio * 10)
		if stage > 9: stage = 9
		if stage < 0: stage = 0
		
		tex_index = self.world.destroy_textures[stage]
		
		# We need to construct geometry for the cube overlay
		# Slightly larger than 1.0 to prevent z-fighting, or use polygon offset
		# Using scaling in logic is easier for now.
		
		# Reuse hand logic approach? No, easier to just build vertices relative to block.
		bx, by, bz = self.breaking_pos
		
		# We need to construct geometry for the cube overlay
		# Slightly larger than 1.0 to prevent z-fighting
		
		bx, by, bz = self.breaking_pos
		
		# Block Center is at bx, by, bz
		# Extent is +/- 0.5
		eps = 0.002
		x1, y1, z1 = bx - 0.5 - eps, by - 0.5 - eps, bz - 0.5 - eps
		x2, y2, z2 = bx + 0.5 + eps, by + 0.5 + eps, bz + 0.5 + eps
		
		w = tex_index
		
		# Face Helper
		def face(coords, uvs):
			res = []
			for i in range(4):
				# Pos
				res.extend(coords[i])
				# Tex
				res.extend((uvs[i][0], uvs[i][1], w))
				# Shade (0.7 to make it darker)
				res.append(0.7)
			return res
			
		verts = []
		# Note: Order and UVs must match standard cube mapping
		# Right (+X)
		verts.extend(face([(x2,y2,z2), (x2,y1,z2), (x2,y1,z1), (x2,y2,z1)], [(0,1), (0,0), (1,0), (1,1)]))
		# Left (-X)
		verts.extend(face([(x1,y2,z1), (x1,y1,z1), (x1,y1,z2), (x1,y2,z2)], [(0,1), (0,0), (1,0), (1,1)])) 
		# Top (+Y)
		verts.extend(face([(x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1)], [(0,1), (1,1), (1,0), (0,0)]))
		# Bottom (-Y)
		verts.extend(face([(x1,y1,z1), (x2,y1,z1), (x2,y1,z2), (x1,y1,z2)], [(0,1), (1,1), (1,0), (0,0)]))
		# Front (+Z)
		verts.extend(face([(x1,y2,z2), (x1,y1,z2), (x2,y1,z2), (x2,y2,z2)], [(0,1), (0,0), (1,0), (1,1)]))
		# Back (-Z)
		verts.extend(face([(x2,y2,z1), (x2,y1,z1), (x1,y1,z1), (x1,y2,z1)], [(0,1), (0,0), (1,0), (1,1)]))
		
		# Upload
		gl.glBindVertexArray(self.breaking_vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.breaking_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(verts) * 4, (gl.GLfloat * len(verts))(*verts), gl.GL_STREAM_DRAW)
		
		stride = 7 * 4
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
		gl.glEnableVertexAttribArray(0)
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
		gl.glEnableVertexAttribArray(1)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 24)
		gl.glEnableVertexAttribArray(2)
		
		# Setup Render State
		self.shader.use() # Ensure shader is bound
		
		# MVP
		m = matrix.Matrix()
		m.load_identity()
		mvp = self.player.p_matrix * self.player.mv_matrix * m
		self.shader.uniform_matrix(self.player.shader_matrix_location, mvp)
		
		# Enable Blend
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		
		# Draw
		gl.glDrawArrays(gl.GL_QUADS, 0, 24)
		
		# Restore
		gl.glDisable(gl.GL_BLEND)

	def on_key_release(self, key, modifiers):
		if not self.mouse_captured:
			return

		if key == pyglet.window.key.D:
			self.player.input[0] -= 1
		elif key == pyglet.window.key.A:
			self.player.input[0] += 1
		elif key == pyglet.window.key.W:
			self.player.input[2] -= 1
		elif key == pyglet.window.key.S:
			self.player.input[2] += 1

		elif key == pyglet.window.key.SPACE:
			self.player.input[1] -= 1
		elif key == pyglet.window.key.LSHIFT:
			self.player.crouching = False
		elif key == pyglet.window.key.LCTRL:
			self.player.sprinting = False
		# Removed LCTRL speed reset as it's now handled by state
		# elif key == pyglet.window.key.LCTRL:
		# 	self.player.target_speed = player.WALKING_SPEED


class Game:
	def __init__(self):
		self.config = gl.Config(double_buffer=True, major_version=3, minor_version=3, depth_size=16)
		self.window = Window(
			config=self.config, width=800, height=600, caption="PythonCraft v8.0", resizable=True, vsync=False
		)

	def run(self):
		pyglet.app.run()


if __name__ == "__main__":
	game = Game()
	game.run()
