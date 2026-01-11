import math

class Frustum:
	def __init__(self):
		self.cam_pos = (0, 0, 0)
		self.forward = (0, 0, 1)
		self.fov_cos = math.cos(math.radians(110 / 2)) # Wide FOV for safety

	def update(self, position, rotation):
		# Rotation: (yaw, pitch)
		yaw, pitch = rotation
		
		# Match Player Movement Logic from player.py lines 103-106
		# Forward (W key) implies movement along (cos(yaw), sin(yaw))
		# Camera looks -Z by default, rotated by Yaw.
		# Adding 90 degrees fixed it previously.
		
		# yaw += math.pi / 2 # Adjust for camera forward
		
		fx = math.cos(yaw + math.pi / 2)
		fz = math.sin(yaw + math.pi / 2)
		
		# Normalize (2D)
		l = math.sqrt(fx*fx + fz*fz)
		if l > 0:
			fx /= l
			fz /= l
			
		self.cam_pos = position
		self.forward = (fx, 0, fz)

	def is_box_visible(self, min_x, min_y, min_z, max_x, max_y, max_z):
		# Simple Directional Check
		# Check Block Center
		cx = (min_x + max_x) * 0.5
		cz = (min_z + max_z) * 0.5
		
		# Vector to chunk
		dx = cx - self.cam_pos[0]
		dz = cz - self.cam_pos[2]
		
		dist_sq = dx*dx + dz*dz
		
		# Always draw close chunks (radius 8 blocks ~ 0.5 chunk)
		if dist_sq < 16*16:
			return True
			
		# Normalize direction
		dist = math.sqrt(dist_sq)
		dx /= dist
		dz /= dist
		
		# Dot Product
		dot = dx * self.forward[0] + dz * self.forward[2]
		
		# Check against FOV Cone
		# If dot > cos(angle), it's in front
		if dot > self.fov_cos:
			return True
			
		return False
