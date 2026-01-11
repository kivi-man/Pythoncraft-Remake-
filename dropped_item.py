import math
import random
import pyglet
from pyglet import gl
import matrix

class DroppedItem:
	def __init__(self, world, pos, block_type, count=1, velocity=None):
		self.world = world
		self.position = list(pos) # [x, y, z]
		self.block_type = block_type
		self.count = count
		
		# Physics
		if velocity:
			self.velocity = list(velocity)
		else:
			self.velocity = [random.uniform(-2, 2), random.uniform(2, 5), random.uniform(-2, 2)]
		
		self.on_ground = False
		self.gravity = -15.0
		self.bounce_factor = 0.5
		
		# Animation
		self.rotation = 0.0 # Y-axis rotation
		self.age = 0.0
		self.bob_offset = 0.0
		
		# Lifecycle
		self.dead = False
		self.pickup_delay = 1.0 # Seconds before can be picked up
		
		# Visuals
		self.scale = 0.25
		self.vao = None
		self.vbo = None
		self.vertex_count = 0
		self._create_mesh()

	def _create_mesh(self):
		# Generate mesh for a single small block
		# Reusing simple block generation logic
		block = self.world.block_types[self.block_type]
		if not block: return
		
		# We need to construct vertices relative to 0,0,0
		verts = []
		
		# Helper for faces - RETURNS 6 Vertices (2 Triangles)
		def face(coords, uvs, shade):
			res = []
			
			# Tri 1: 0, 1, 2
			indices = [0, 1, 2, 0, 2, 3]
			
			for idx in indices:
				# Pos
				res.extend(coords[idx])
				# Tex
				res.extend(uvs[idx])
				# Shade
				res.append(shade)
			
			return res

		# Cube corners centered
		s = 0.5 # Extent from center (size 1.0)
		x1, y1, z1 = -s, -s, -s
		x2, y2, z2 =  s,  s,  s
		
		# Function to extract u,v,w tuple from the flat list
		def get_uvw(flat_list, idx):
			return (flat_list[idx*3], flat_list[idx*3+1], flat_list[idx*3+2])

		def get_face_uvs(face_index):
			f_idx = face_index if face_index < len(block.tex_coords) else 0
			fl = block.tex_coords[f_idx]
			return [get_uvw(fl, 0), get_uvw(fl, 1), get_uvw(fl, 2), get_uvw(fl, 3)]

		# Generate all 6 faces for complete look
		# Top
		verts.extend(face([(x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1)], get_face_uvs(2), 1.0))
		# Bottom
		verts.extend(face([(x1,y1,z2), (x2,y1,z2), (x2,y1,z1), (x1,y1,z1)], get_face_uvs(3), 0.5))
		# Right
		verts.extend(face([(x2,y2,z2), (x2,y1,z2), (x2,y1,z1), (x2,y2,z1)], get_face_uvs(0), 0.6))
		# Left
		verts.extend(face([(x1,y2,z1), (x1,y1,z1), (x1,y1,z2), (x1,y2,z2)], get_face_uvs(1), 0.6))
		# Front
		verts.extend(face([(x1,y2,z2), (x1,y1,z2), (x2,y1,z2), (x2,y2,z2)], get_face_uvs(4), 0.8))
		# Back
		verts.extend(face([(x2,y2,z1), (x2,y1,z1), (x1,y1,z1), (x1,y2,z1)], get_face_uvs(5), 0.8))
		
		self.vertex_count = len(verts) // 7
		
		# Upload to GPU
		self.vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.vao)
		gl.glBindVertexArray(self.vao)
		
		self.vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.vbo)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
		
		c_verts = (gl.GLfloat * len(verts))(*verts)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(verts) * 4, c_verts, gl.GL_STATIC_DRAW)
		
		# Layout: 3 Pos, 3 Tex, 1 Shade
		stride = 7 * 4
		# Pos
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
		gl.glEnableVertexAttribArray(0)
		# Tex
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
		gl.glEnableVertexAttribArray(1)
		# Shade
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 24)
		gl.glEnableVertexAttribArray(2)
		
		gl.glBindVertexArray(0)

	def update(self, dt, player):
		self.age += dt
		
		# Gravity
		self.velocity[1] += self.gravity * dt
		
		# Bounding Box Size (Radius)
		r = 0.15 
		
		# Helper collision check
		def check_collisions(pos):
			# check a few points around center to simulate volume
			# floor coords
			min_x, max_x = math.floor(pos[0] - r), math.floor(pos[0] + r)
			min_y, max_y = math.floor(pos[1] - r), math.floor(pos[1] + r)
			min_z, max_z = math.floor(pos[2] - r), math.floor(pos[2] + r)
			
			for bx in range(min_x, max_x + 1):
				for by in range(min_y, max_y + 1):
					for bz in range(min_z, max_z + 1):
						if self.world.get_block_number((bx, by, bz)):
							return True
			return False

		# Integrate Axes Separately
		
		# X Axis
		self.position[0] += self.velocity[0] * dt
		if check_collisions(self.position):
			self.position[0] -= self.velocity[0] * dt # Undo
			self.velocity[0] *= -0.5 # Bounce

		# Z Axis
		self.position[2] += self.velocity[2] * dt
		if check_collisions(self.position):
			self.position[2] -= self.velocity[2] * dt # Undo
			self.velocity[2] *= -0.5 # Bounce

		# Y Axis
		self.position[1] += self.velocity[1] * dt
		if check_collisions(self.position):
			self.position[1] -= self.velocity[1] * dt # Undo
			
			# Ground Friction
			if self.velocity[1] < 0: # Hit floor
				self.on_ground = True
				self.velocity[0] *= 0.8
				self.velocity[2] *= 0.8
			elif self.velocity[1] > 0: # Hit ceiling
				self.velocity[0] *= 0.95
				self.velocity[2] *= 0.95
				
			self.velocity[1] *= -0.25 # Bounce Y
			if abs(self.velocity[1]) < 0.5: self.velocity[1] = 0
		else:
			self.on_ground = False

		# Magnet and Pickup
		px, py, pz = player.position
		dist_sq = (self.position[0]-px)**2 + (self.position[1]-py)**2 + (self.position[2]-pz)**2
		
		if self.age > self.pickup_delay:
			# Pickup (Very close)
			if dist_sq < 1.5**2: 
				return True 
				
			# Magnet (Close range)
			if dist_sq < 3.0**2:
				# Move towards player
				speed = 6.0
				dist = math.sqrt(dist_sq)
				dx = (px - self.position[0]) / dist
				dy = (py - self.position[1]) / dist
				dz = (pz - self.position[2]) / dist
				
				self.velocity[0] += dx * speed * dt
				self.velocity[1] += dy * speed * dt
				self.velocity[2] += dz * speed * dt
				self.on_ground = False
				
		# Animation
		self.rotation += 90 * dt
		# Reduced bobbing (floating)
		self.bob_offset = math.sin(self.age * 3) * 0.05
		
		return False

	def draw(self, shader_matrix_loc):
		if not self.vao: return
		
		m = matrix.Matrix()
		m.load_identity()
		
		# Translate
		m.translate(self.position[0], self.position[1], self.position[2])
		
		# Rotate
		# Rotate continuous around Y
		m.rotate(math.radians(self.rotation), 0, 1, 0)
		
		# Scale
		s = self.scale
		m.scale(s, s, s)
		
		# Bobbing? Done in translate usually? Wait, I didn't add bob to position.
		# I can do it in matrix
		# m.translate(0, self.bob_offset, 0) # Apply bob separately
		
		# Wait, order: Scale -> Rotate -> Translate
		# My translate is first (world pos).
		# To bob, I should adjust Y before setting matrix? Or add translation.
		# m.data[3][1] += self.bob_offset
		
		# Let's rebuild matrix correctly
		m.load_identity()
		m.translate(self.position[0], self.position[1] + self.bob_offset, self.position[2])
		m.rotate(math.radians(self.rotation), 0, 1, 0)
		m.scale(s, s, s)
		
		# We need to get the FULL MVP matrix or Model Matrix?
		# The main shader usually expects MVP in `player.shader_matrix_location`? 
		# No, `main.py` calculates MVP = P * V * M.
		# I should pass Model Matrix to `main.py` to combine? 
		# Or `main.py` passes P*V and I multiply?
		# `main.py` shader uniform `matrix` IS model_view_projection.
		
		# So I need P and V from player outside.
		# I'll handle this in `main.py` passing VP.
		pass # Logic moved to main for draw call to access player matrices

	def get_model_matrix(self):
		m = matrix.Matrix()
		m.load_identity()
		m.translate(self.position[0], self.position[1] + self.bob_offset, self.position[2])
		m.rotate(math.radians(self.rotation), 0, 1, 0)
		m.scale(self.scale, self.scale, self.scale)
		return m
