import ctypes
import math

import pyglet.gl as gl

import subchunk

CHUNK_WIDTH = 16
CHUNK_HEIGHT = 16
CHUNK_LENGTH = 16


class Chunk:
	def __init__(self, world, chunk_position):
		self.world = world

		self.modified = False
		self.chunk_position = chunk_position

		self.position = (
			self.chunk_position[0] * CHUNK_WIDTH,
			self.chunk_position[1] * CHUNK_HEIGHT,
			self.chunk_position[2] * CHUNK_LENGTH,
		)

		self.blocks = [[[0 for z in range(CHUNK_LENGTH)] for y in range(CHUNK_HEIGHT)] for x in range(CHUNK_WIDTH)]

		self.subchunks = {}

		# Subchunks logic
		# CHUNK_HEIGHT is 16, SUBCHUNK_HEIGHT is 16
		# So loops should range(1) for y
		
		# Ensure integer division
		n_sub_x = int(CHUNK_WIDTH / subchunk.SUBCHUNK_WIDTH)
		n_sub_y = int(CHUNK_HEIGHT / subchunk.SUBCHUNK_HEIGHT)
		n_sub_z = int(CHUNK_LENGTH / subchunk.SUBCHUNK_LENGTH)
		
		for x in range(n_sub_x):
			for y in range(n_sub_y):
				for z in range(n_sub_z):
					self.subchunks[(x, y, z)] = subchunk.Subchunk(self, (x, y, z))

		# mesh variables

		# Water mesh variables
		self.water_mesh_vertex_positions = []
		self.water_mesh_tex_coords = []
		self.water_mesh_shading_values = []
		self.water_mesh_index_counter = 0
		self.water_mesh_indices = []
		self.water_mesh_indices_length = 0

		# create VAO and VBO's for Solid blocks
		self.vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.vao)
		gl.glBindVertexArray(self.vao)

		self.vertex_position_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.vertex_position_vbo)
		self.tex_coord_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.tex_coord_vbo)
		self.shading_values_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.shading_values_vbo)
		self.ibo = gl.GLuint(0)
		gl.glGenBuffers(1, self.ibo)

		# create VAO and VBO's for Water blocks
		self.water_vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.water_vao)
		gl.glBindVertexArray(self.water_vao)

		self.water_vertex_position_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.water_vertex_position_vbo)
		self.water_tex_coord_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.water_tex_coord_vbo)
		self.water_shading_values_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.water_shading_values_vbo)
		self.water_ibo = gl.GLuint(0)
		gl.glGenBuffers(1, self.water_ibo)

	def update_subchunk_meshes(self, update_only_water=False):
		for subchunk_position in self.subchunks:
			subchunk = self.subchunks[subchunk_position]
			subchunk.update_mesh(update_only_water=update_only_water)

	def update_at_position(self, position):
		x, y, z = position

		lx = int(x % subchunk.SUBCHUNK_WIDTH)
		ly = int(y % subchunk.SUBCHUNK_HEIGHT)
		lz = int(z % subchunk.SUBCHUNK_LENGTH)

		clx, cly, clz = self.world.get_local_position(position)

		sx = math.floor(clx / subchunk.SUBCHUNK_WIDTH)
		sy = math.floor(cly / subchunk.SUBCHUNK_HEIGHT)
		sz = math.floor(clz / subchunk.SUBCHUNK_LENGTH)

		self.subchunks[(sx, sy, sz)].update_mesh()

		def try_update_subchunk_mesh(subchunk_position):
			if subchunk_position in self.subchunks:
				self.subchunks[subchunk_position].update_mesh()

		if lx == subchunk.SUBCHUNK_WIDTH - 1:
			try_update_subchunk_mesh((sx + 1, sy, sz))
		if lx == 0:
			try_update_subchunk_mesh((sx - 1, sy, sz))

		if ly == subchunk.SUBCHUNK_HEIGHT - 1:
			try_update_subchunk_mesh((sx, sy + 1, sz))
		if ly == 0:
			try_update_subchunk_mesh((sx, sy - 1, sz))

		if lz == subchunk.SUBCHUNK_LENGTH - 1:
			try_update_subchunk_mesh((sx, sy, sz + 1))
		if lz == 0:
			try_update_subchunk_mesh((sx, sy, sz - 1))

	def update_mesh(self, update_only_water=False):
		# combine all the small subchunk meshes into one big chunk mesh

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


		for subchunk_position in self.subchunks:
			subchunk = self.subchunks[subchunk_position]

			try:
				if not update_only_water:
					# Solid Mesh
					# Calculate vertex offset based on current number of vertices
					# Vertices are stored as (x,y,z), so divide by 3
					vertex_offset = len(self.mesh_vertex_positions) // 3
					
					self.mesh_vertex_positions.extend(subchunk.mesh_vertex_positions)
					self.mesh_tex_coords.extend(subchunk.mesh_tex_coords)
					self.mesh_shading_values.extend(subchunk.mesh_shading_values)

					# Shift indices by the vertex offset
					mesh_indices = [index + vertex_offset for index in subchunk.mesh_indices]
					self.mesh_indices.extend(mesh_indices)
					
					# Update counter (just used for 'has data' check later)
					self.mesh_index_counter += len(mesh_indices)
				
				# Water Mesh
				# Water Mesh
				water_vertex_offset = len(self.water_mesh_vertex_positions) // 3
				
				self.water_mesh_vertex_positions.extend(subchunk.water_mesh_vertex_positions)
				self.water_mesh_tex_coords.extend(subchunk.water_mesh_tex_coords)
				self.water_mesh_shading_values.extend(subchunk.water_mesh_shading_values)
				
				water_indices = [index + water_vertex_offset for index in subchunk.water_mesh_indices]
				self.water_mesh_indices.extend(water_indices)
				self.water_mesh_index_counter += len(water_indices)
			except AttributeError as e:
				print(f"CRITICAL ERROR in update_mesh: {e}")
				print(f"Subchunk: {subchunk_position}")
				if not hasattr(self, 'water_mesh_index_counter'):
					print("SELF MISSING water_mesh_index_counter")
				if not hasattr(subchunk, 'water_mesh_index_counter'):
					print("SUBCHUNK MISSING water_mesh_index_counter")
				raise e

		# send the full mesh data to the GPU and free the memory used client-side (we don't need it anymore)
		
		if not update_only_water:
			# Solid Mesh
			self.mesh_indices_length = len(self.mesh_indices)
			self.send_mesh_data_to_gpu()

			del self.mesh_vertex_positions
			del self.mesh_tex_coords
			del self.mesh_shading_values
			del self.mesh_indices
		
		# Water Mesh
		self.water_mesh_indices_length = len(self.water_mesh_indices)
		self.send_water_mesh_data_to_gpu()
		
		del self.water_mesh_vertex_positions
		del self.water_mesh_tex_coords
		del self.water_mesh_shading_values
		del self.water_mesh_indices

	def send_mesh_data_to_gpu(self):  # pass mesh data to gpu
		if not getattr(self, 'mesh_index_counter', 0):
			return

		gl.glBindVertexArray(self.vao)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vertex_position_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLfloat * len(self.mesh_vertex_positions)),
			(gl.GLfloat * len(self.mesh_vertex_positions))(*self.mesh_vertex_positions),
			gl.GL_STATIC_DRAW,
		)

		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.tex_coord_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLfloat * len(self.mesh_tex_coords)),
			(gl.GLfloat * len(self.mesh_tex_coords))(*self.mesh_tex_coords),
			gl.GL_STATIC_DRAW,
		)

		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.shading_values_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLfloat * len(self.mesh_shading_values)),
			(gl.GLfloat * len(self.mesh_shading_values))(*self.mesh_shading_values),
			gl.GL_STATIC_DRAW,
		)

		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ibo)
		gl.glBufferData(
			gl.GL_ELEMENT_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLuint * self.mesh_indices_length),
			(gl.GLuint * self.mesh_indices_length)(*self.mesh_indices),
			gl.GL_STATIC_DRAW,
		)
		
	def send_water_mesh_data_to_gpu(self):
		if not getattr(self, 'water_mesh_index_counter', 0):
			return

		gl.glBindVertexArray(self.water_vao)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.water_vertex_position_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLfloat * len(self.water_mesh_vertex_positions)),
			(gl.GLfloat * len(self.water_mesh_vertex_positions))(*self.water_mesh_vertex_positions),
			gl.GL_STATIC_DRAW,
		)

		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.water_tex_coord_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLfloat * len(self.water_mesh_tex_coords)),
			(gl.GLfloat * len(self.water_mesh_tex_coords))(*self.water_mesh_tex_coords),
			gl.GL_STATIC_DRAW,
		)

		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.water_shading_values_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLfloat * len(self.water_mesh_shading_values)),
			(gl.GLfloat * len(self.water_mesh_shading_values))(*self.water_mesh_shading_values),
			gl.GL_STATIC_DRAW,
		)

		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.water_ibo)
		gl.glBufferData(
			gl.GL_ELEMENT_ARRAY_BUFFER,
			ctypes.sizeof(gl.GLuint * self.water_mesh_indices_length),
			(gl.GLuint * self.water_mesh_indices_length)(*self.water_mesh_indices),
			gl.GL_STATIC_DRAW,
		)

	def draw(self, pass_type='all'):
		if pass_type in ['all', 'solid']:
			if getattr(self, 'mesh_index_counter', 0):
				gl.glBindVertexArray(self.vao)
				gl.glDrawElements(gl.GL_TRIANGLES, self.mesh_indices_length, gl.GL_UNSIGNED_INT, None)
				
		if pass_type in ['all', 'water']:
			if getattr(self, 'water_mesh_index_counter', 0):
				gl.glBindVertexArray(self.water_vao)
				gl.glDrawElements(gl.GL_TRIANGLES, self.water_mesh_indices_length, gl.GL_UNSIGNED_INT, None)

	def delete(self):
		gl.glDeleteBuffers(1, self.vertex_position_vbo)
		gl.glDeleteBuffers(1, self.tex_coord_vbo)
		gl.glDeleteBuffers(1, self.shading_values_vbo)
		gl.glDeleteBuffers(1, self.ibo)
		gl.glDeleteVertexArrays(1, self.vao)

		gl.glDeleteBuffers(1, self.water_vertex_position_vbo)
		gl.glDeleteBuffers(1, self.water_tex_coord_vbo)
		gl.glDeleteBuffers(1, self.water_shading_values_vbo)
		gl.glDeleteBuffers(1, self.water_ibo)
		gl.glDeleteVertexArrays(1, self.water_vao)

