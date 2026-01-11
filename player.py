import math
import entity
import matrix

WALKING_SPEED = 4.317
SPRINTING_SPEED = 7  # faster than in Minecraft, feels better
CROUCHING_SPEED = 1.5


class Player(entity.Entity):
	def __init__(self, world, shader, width, height):
		super().__init__(world)

		self.view_width = width
		self.view_height = height

		# create matrices

		self.mv_matrix = matrix.Matrix()
		self.p_matrix = matrix.Matrix()

		# shaders

		self.shader = shader
		self.shader_matrix_location = self.shader.find_uniform(b"matrix")

		# Camera variables
		self.eyelevel = self.height - 0.2
		self.input = [0, 0, 0]
		self.camera_mode = 0 # 0: First, 1: Third Back, 2: Third Front
		self.current_camera_dist = 4.0
		self.last_dt = 0.016
		
		# Movement states
		self.sprinting = False
		self.crouching = False
		
		self.target_speed = WALKING_SPEED
		self.speed = self.target_speed

	@property
	def submersion_factor(self):
		x, y, z = self.position
		head_y = y + self.eyelevel
		
		# Find block visually containing the head (assuming centered models)
		bx = math.floor(x + 0.5)
		by = math.floor(head_y + 0.5)
		bz = math.floor(z + 0.5)
		
		block_num = self.world.get_block_number((bx, by, bz))
		
		if block_num not in [8, 9]:
			return 0.0
			
		level = self.world.block_metadata.get_water_level((bx, by, bz))
		# Calculate visual top height relative to block center
		h = max(0.1, 1.0 - (level / 5.0) ** 1.5) if level else 1.0
		
		# Visual Top Y in World Space (Block Center Y + (Height - 0.5))
		visual_top_y = by + (h - 0.5)
		
		diff = visual_top_y - head_y
		
		# Smooth transition zone +/- 0.1 units (average at surface)
		# T = 0.5 when diff = 0 (exactly at surface)
		t = (diff + 0.1) / 0.2
		return max(0.0, min(1.0, t))

	@property
	def is_underwater(self):
		return self.submersion_factor > 0.0

	def update(self, delta_time):
		self.last_dt = delta_time
		# process input
		
		if self.crouching:
			self.target_speed = CROUCHING_SPEED
			self.safe_walk = True
		elif self.sprinting:
			self.target_speed = SPRINTING_SPEED
			self.safe_walk = False
		else:
			self.target_speed = WALKING_SPEED
			self.safe_walk = False

		if delta_time * 20 > 1:
			self.speed = self.target_speed
		else:
			self.speed += (self.target_speed - self.speed) * delta_time * 20

		multiplier = self.speed * (1, 2)[self.flying]

		if self.flying and self.input[1]:
			self.accel[1] = self.input[1] * multiplier
		
		# Swimming: hold space to swim upward
		elif self.in_water and self.input[1] > 0:
			self.velocity[1] = 5  # Swim upward speed (balanced - not too fast)

		if self.input[0] or self.input[2]:
			angle = self.rotation[0] - math.atan2(self.input[2], self.input[0]) + math.tau / 4

			self.accel[0] = math.cos(angle) * multiplier
			self.accel[2] = math.sin(angle) * multiplier

		if not self.flying and not self.in_water and self.input[1] > 0:
			self.jump()

		# process physics & collisions &c

		super().update(delta_time)

	def get_collided_dist(self, target_dist):
		if self.camera_mode == 0: return 0
		
		# Start at head
		hx, hy, hz = self.position[0], self.position[1] + self.eyelevel, self.position[2]
		if self.crouching: hy -= 0.2
		
		# Direction logic
		# Mode 1 (Back): +dist on Camera Z (Local Backward)
		# Mode 2 (Front): +dist on Camera Z (Local Forward after 180 rotation)
		
		# Camera orientation relative to head
		yaw = self.rotation[0]
		pitch = self.rotation[1]
		
		# Camera local Z-forward vector in world space:
		# f_x = -sin(yaw) * cos(pitch)
		# f_y = sin(pitch)
		# f_z = -cos(yaw) * cos(pitch)
		
		# Local Z-backward vector:
		# b_x = sin(yaw) * cos(pitch)
		# b_y = -sin(pitch)
		# b_z = cos(yaw) * cos(pitch)
		
		mult = 1.0 if self.camera_mode == 1 else -1.0
		dx = math.sin(yaw) * math.cos(pitch) * mult
		dy = -math.sin(pitch) * mult
		dz = math.cos(yaw) * math.cos(pitch) * mult
		
		# Raymarch / Sample collision
		# We'll check 20 steps for smoothness
		steps = 20
		radius = 0.2 # Safety margin
		
		for i in range(1, steps + 1):
			check_dist = (i / steps) * target_dist
			px = hx + dx * check_dist
			py = hy + dy * check_dist
			pz = hz + dz * check_dist
			
			collision = False
			# check box around point
			for ox in [-radius, radius]:
				for oy in [-radius, radius]:
					for oz in [-radius, radius]:
						if self.world.get_block_number((math.floor(px+ox), math.floor(py+oy), math.floor(pz+oz))):
							collision = True
							break
					if collision: break
				if collision: break
				
			if collision:
				# Return previous safe distance (approx)
				return max(0.5, check_dist - 0.4)
				
		return target_dist

	def update_matrices(self):
		# create projection matrix

		self.p_matrix.load_identity()

		self.p_matrix.perspective(
			90 + 10 * (self.speed - WALKING_SPEED) / (SPRINTING_SPEED - WALKING_SPEED),
			float(self.view_width) / self.view_height,
			0.1,
			500,
		)

		# create modelview matrix
		
		# Adjust eye level for crouching
		current_eyelevel = self.eyelevel
		if self.crouching:
			current_eyelevel -= 0.2 # Lower camera

		self.mv_matrix.load_identity()
		
		# 3rd Person Offset: Applied FIRST on identity
		target_dist = 0.0
		if self.camera_mode != 0:
			target_dist = self.get_collided_dist(4.0)
		
		# Smooth Lerp for camera distance
		# 10.0 factor for speed
		lerp_speed = 10.0
		self.current_camera_dist += (target_dist - self.current_camera_dist) * min(1.0, self.last_dt * lerp_speed)
		
		if self.camera_mode != 0 or self.current_camera_dist > 0.01:
			# First, translate camera back
			self.mv_matrix.translate(0, 0, -self.current_camera_dist)
			
			# For Front View (Mode 2): Rotate 180 degrees AFTER translation
			# This puts the camera in front of the character, looking back at them
			if self.camera_mode == 2:
				self.mv_matrix.rotate_2d(math.pi, 0)

		# Player Orientation and Position (World -> Eye)
		self.mv_matrix.rotate_2d(self.rotation[0] + math.tau / 4, self.rotation[1])
		self.mv_matrix.translate(-self.position[0], -self.position[1] - current_eyelevel, -self.position[2])

		# modelviewprojection matrix
		mvp_matrix = self.p_matrix * self.mv_matrix
		
		self.shader.use()
		self.shader.uniform_matrix(self.shader_matrix_location, mvp_matrix)
