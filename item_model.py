import pyglet
import math

class ItemModel:
	def __init__(self, texture_path):
		self.texture = pyglet.image.load(texture_path)
		self.image_data = self.texture.get_image_data()
		self.width = self.texture.width
		self.height = self.texture.height
		self.pixels = self.image_data.get_data('RGBA', self.width * 4)

	def get_pixel(self, x, y):
		if x < 0 or x >= self.width or y < 0 or y >= self.height:
			return (0, 0, 0, 0)
		
		# Image data is usually bottom-to-top in pyglet
		idx = (y * self.width + x) * 4
		return (self.pixels[idx], self.pixels[idx+1], self.pixels[idx+2], self.pixels[idx+3])

	def generate_mesh(self, texture_index=0, scale=0.0625):
		# Generates a 3D mesh by extruding non-transparent pixels
		# scale 0.0625 is 1/16, meaning a 16x16 sprite is 1x1 in world units
		
		vertices = []
		tex_coords = []
		shading = []
		indices = []
		index_offset = 0

		# Center the model
		off_x = -self.width / 2 * scale
		off_y = -self.height / 2 * scale
		thickness = scale # 1 pixel deep

		for py in range(self.height):
			for px in range(self.width):
				r, g, b, a = self.get_pixel(px, py)
				if a < 128: # Transparent
					continue

				self.add_pixel_cube(px, py, vertices, tex_coords, shading, indices, index_offset, scale, off_x, off_y, thickness, texture_index)
				index_offset = len(vertices) // 3

		return vertices, tex_coords, shading, indices

	def add_pixel_cube(self, px, py, vertices, tex_coords, shading, indices, base_idx, scale, off_x, off_y, thickness, texture_index):
		# Geometry for a single pixel-block
		x = off_x + px * scale
		y = off_y + py * scale
		z_front = thickness / 2
		z_back = -thickness / 2

		# Colors/UVs for this pixel
		# We'll map the UV to the exact pixel coordinate in the texture
		# Note: pyglet UVs are 0..1
		u1 = px / self.width
		v1 = py / self.height
		u2 = (px + 1) / self.width
		v2 = (py + 1) / self.height

		# Neighbor check
		neighbors = [
			(1, 0), (-1, 0), (0, 1), (0, -1)
		]
		
		# 1. Front Face
		vertices.extend([
			x, y, z_front,
			x + scale, y, z_front,
			x + scale, y + scale, z_front,
			x, y + scale, z_front
		])
		tex_coords.extend([u1, v1, texture_index, u2, v1, texture_index, u2, v2, texture_index, u1, v2, texture_index])
		shading.extend([1.0, 1.0, 1.0, 1.0])
		indices.extend([base_idx, base_idx+1, base_idx+2, base_idx, base_idx+2, base_idx+3])
		base_idx += 4

		# 2. Back Face
		vertices.extend([
			x + scale, y, z_back,
			x, y, z_back,
			x, y + scale, z_back,
			x + scale, y + scale, z_back
		])
		tex_coords.extend([u2, v1, texture_index, u1, v1, texture_index, u1, v2, texture_index, u2, v2, texture_index])
		shading.extend([0.6, 0.6, 0.6, 0.6]) # Slightly darker back
		indices.extend([base_idx, base_idx+1, base_idx+2, base_idx, base_idx+2, base_idx+3])
		base_idx += 4

		# 3. Sides (only if next pixel is transparent)
		side_data = [
			(1, 0, [x+scale, y, z_front, x+scale, y, z_back, x+scale, y+scale, z_back, x+scale, y+scale, z_front], 0.8), # Right
			(-1, 0, [x, y, z_back, x, y, z_front, x, y+scale, z_front, x, y+scale, z_back], 0.8), # Left
			(0, 1, [x, y+scale, z_front, x+scale, y+scale, z_front, x+scale, y+scale, z_back, x, y+scale, z_back], 0.9), # Top
			(0, -1, [x, y, z_back, x+scale, y, z_back, x+scale, y, z_front, x, y, z_front], 0.7), # Bottom
		]

		for dx, dy, verts, shade in side_data:
			_, _, _, a = self.get_pixel(px + dx, py + dy)
			if a < 128:
				vertices.extend(verts)
				tex_coords.extend([u1, v1, texture_index, u2, v1, texture_index, u2, v2, texture_index, u1, v2, texture_index]) 
				shading.extend([shade] * 4)
				indices.extend([base_idx, base_idx+1, base_idx+2, base_idx, base_idx+2, base_idx+3])
				base_idx += 4
