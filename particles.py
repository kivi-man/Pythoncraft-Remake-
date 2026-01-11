import random
import math
import pyglet.gl as gl
import matrix

class Particle:
	def __init__(self, position, velocity, texture_index):
		self.position = list(position)
		self.velocity = list(velocity)
		self.texture_index = texture_index
		
		self.lifetime = 1.0 + random.random() * 0.5 # 1.0 to 1.5 seconds
		self.total_lifetime = self.lifetime
		self.size = 0.1 + random.random() * 0.1 # 0.1 to 0.2 size
		
		# Pick a random 4x4 pixel area from the 16x16 texture
		# UV coordinates are 0.0 to 1.0
		# 4/16 = 0.25
		uv_size = 0.25
		u = random.randint(0, 3) * 0.25
		v = random.randint(0, 3) * 0.25
		self.uv = (u, v, u + uv_size, v + uv_size)

	def update(self, delta_time):
		# Gravity
		self.velocity[1] -= 15.0 * delta_time 
		
		# Move
		self.position[0] += self.velocity[0] * delta_time
		self.position[1] += self.velocity[1] * delta_time
		self.position[2] += self.velocity[2] * delta_time
		
		# Simulate simple drag
		self.velocity[0] *= 0.95
		self.velocity[2] *= 0.95
		
		self.lifetime -= delta_time

class ParticleSystem:
	def __init__(self, shader):
		self.particles = []
		self.shader = shader
		
		self.vao = gl.GLuint(0)
		self.vbo = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.vao)
		gl.glGenBuffers(1, self.vbo)

	def spawn(self, position, texture_index, count=1, speed=1.0, is_explosion=False):
		for _ in range(count):
			# Random spread mechanism
			# For explosions, spread out from center
			# For simple digging, smaller spread
			
			spread = 0.3 if is_explosion else 0.1
			
			px = position[0] + (random.random() * 2 - 1) * 0.5
			py = position[1] + (random.random() * 2 - 1) * 0.5
			pz = position[2] + (random.random() * 2 - 1) * 0.5
			
			# Velocity
			vx = (random.random() * 2 - 1) * speed
			vy = (random.random() * 1.5) * speed # Upward bias
			vz = (random.random() * 2 - 1) * speed
			
			if is_explosion:
				# Explosion visuals: faster, more spread
				vx *= 2
				vy += 2 # Initial pop up
				vz *= 2
			
			self.particles.append(Particle((px, py, pz), (vx, vy, vz), texture_index))

	def update(self, delta_time):
		# Update particles and remove dead ones
		# Iterate backwards to safely remove
		for i in range(len(self.particles) - 1, -1, -1):
			particle = self.particles[i]
			particle.update(delta_time)
			if particle.lifetime <= 0:
				self.particles.pop(i)

	def draw(self, player):
		if not self.particles:
			return
			
		# Rebuild mesh dynamicall every frame 
		# (Not efficient for thousands, but fine for < 1000 particles)
		
		verts = []
		
		# Camera right/up vectors for billboarding (optional, but cubes are better for MC style)
		# MC particles are usually 2D sprites always facing camera OR little 3D cubes?
		# Original MC particles are 2D squares that billboard (face camera).
		# Let's do simple 2D quads facing the player for performance and simplicity, 
		# or 3D cubes if we want "pixel" cubes.
		# User said "Pixel... çıksın" (Pixels come out). 2D billboard is standard.
		
		# Simple Billboarding:
		# We need vectors parallel to camera view plane.
		# Since we are in 3D, we can extract camera basis vectors from view matrix?
		# Or just draw axis-aligned cubes? MC particles are often 2D textures on a plane.
		# Let's do mini-cubes for "premium" feel.
		
		for p in self.particles:
			x, y, z = p.position
			s = p.size / 2
			w = p.texture_index
			u1, v1, u2, v2 = p.uv
			
			# Cube Generation (simplified)
			# We'll just generate a small cube at x,y,z
			
			def add_face(p1, p2, p3, p4):
				verts.extend(p1 + (u1, v1, w, 1.0))
				verts.extend(p2 + (u1, v2, w, 1.0))
				verts.extend(p3 + (u2, v2, w, 1.0))
				verts.extend(p4 + (u2, v1, w, 1.0))

			# Vertices for a cube centered at x,y,z with size s*2
			x1, y1, z1 = x-s, y-s, z-s
			x2, y2, z2 = x+s, y+s, z+s
			
			# Just draw 3 visible faces based on random spin? 
			# Or draw all 6. 6 faces * 4 verts = 24 verts per particle.
			# 100 particles = 2400 verts. Trivial.
			
			# Front
			add_face((x1,y2,z2), (x1,y1,z2), (x2,y1,z2), (x2,y2,z2))
			# Back
			add_face((x2,y2,z1), (x2,y1,z1), (x1,y1,z1), (x1,y2,z1))
			# Right
			add_face((x2,y2,z2), (x2,y1,z2), (x2,y1,z1), (x2,y2,z1))
			# Left
			add_face((x1,y2,z1), (x1,y1,z1), (x1,y1,z2), (x1,y2,z2))
			# Top
			add_face((x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1))
			# Bottom
			add_face((x1,y1,z1), (x2,y1,z1), (x2,y1,z2), (x1,y1,z2))

		# Upload
		gl.glBindVertexArray(self.vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(verts) * 4, (gl.GLfloat * len(verts))(*verts), gl.GL_STREAM_DRAW)
		
		stride = 7 * 4
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
		gl.glEnableVertexAttribArray(0)
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
		gl.glEnableVertexAttribArray(1)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 24)
		gl.glEnableVertexAttribArray(2)
		
		# Draw
		self.shader.use()
		
		m = matrix.Matrix()
		m.load_identity()
		mvp = player.p_matrix * player.mv_matrix * m
		self.shader.uniform_matrix(player.shader_matrix_location, mvp)
		
		gl.glDrawArrays(gl.GL_QUADS, 0, len(self.particles) * 24)
