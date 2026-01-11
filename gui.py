import pyglet
from pyglet import gl
import ctypes
import math
import pyglet
from pyglet import gl
import ctypes
import math
import matrix 
import inventory

# Simple Shader for 2D UI (Vertex + Fragment)
item_vertex_source = """#version 330
layout(location = 0) in vec2 position;
layout(location = 1) in vec4 color;

out vec4 frag_color;

uniform mat4 projection;

void main()
{
    gl_Position = projection * vec4(position, 0.0, 1.0);
    frag_color = color;
}
"""

item_fragment_source = """#version 330
in vec4 frag_color;
out vec4 out_color;

void main()
{
    out_color = frag_color;
}
"""

# Shader for 3D Item Icons
icon_vertex_source = """#version 330
layout(location = 0) in vec3 position;
layout(location = 1) in vec3 tex_coords;
layout(location = 2) in float shading;

out vec3 v_tex_coords;
out float v_shading;

uniform mat4 projection;
uniform mat4 model;

void main()
{
    gl_Position = projection * model * vec4(position, 1.0);
    v_tex_coords = tex_coords;
    v_shading = shading;
}
"""

icon_fragment_source = """#version 330
in vec3 v_tex_coords;
in float v_shading;
out vec4 out_color;

uniform sampler2DArray texture_array;

void main()
{
    vec4 tex_color = texture(texture_array, v_tex_coords);
    if(tex_color.a < 0.1) discard;
    out_color = vec4(tex_color.rgb * v_shading, tex_color.a);
}
"""

class InventoryRenderer:
	def __init__(self, inventory, world, width, height):
		self.inventory = inventory
		self.world = world
		self.width = width
		self.height = height
		self.scale = 40 # Size of slots in pixels
		
		self.menu_open = False
		
		# 2D Shader
		self.shader = pyglet.graphics.shader.ShaderProgram(
			pyglet.graphics.shader.Shader(item_vertex_source, 'vertex'),
			pyglet.graphics.shader.Shader(item_fragment_source, 'fragment')
		)
		self.proj_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'projection'))
		
		# 3D Icon Shader
		self.icon_shader = pyglet.graphics.shader.ShaderProgram(
			pyglet.graphics.shader.Shader(icon_vertex_source, 'vertex'),
			pyglet.graphics.shader.Shader(icon_fragment_source, 'fragment')
		)
		self.icon_proj_loc = gl.glGetUniformLocation(self.icon_shader.id, ctypes.create_string_buffer(b'projection'))
		self.icon_model_loc = gl.glGetUniformLocation(self.icon_shader.id, ctypes.create_string_buffer(b'model'))
		self.icon_tex_loc = gl.glGetUniformLocation(self.icon_shader.id, ctypes.create_string_buffer(b'texture_array'))

		# Text Labels for Hotbar
		self.label_batch = pyglet.graphics.Batch()
		self.hotbar_labels = []
		for i in range(9):
			label = pyglet.text.Label(
				'',
				font_name='Arial',
				font_size=10,
				x=0, y=0,
				anchor_x='right', anchor_y='bottom',
				color=(255, 255, 255, 255),
				batch=self.label_batch
			)
			self.hotbar_labels.append(label)
		
		self.title_label = pyglet.text.Label(
			'', font_name='Arial', font_size=12,
			x=0, y=0, anchor_x='center', anchor_y='bottom',
			color=(255, 255, 255, 255), batch=self.label_batch
		)

		# Load Hotbar Textures
		try:
			hotbar_img = pyglet.image.load("textures/hotbar.png")
			hotbar_tex = hotbar_img.get_texture()
			gl.glBindTexture(hotbar_tex.target, hotbar_tex.id)
			gl.glTexParameteri(hotbar_tex.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
			gl.glBindTexture(hotbar_tex.target, 0)
			
			self.hotbar_sprite = pyglet.sprite.Sprite(hotbar_tex)
			
			# Calculate Scale
			self.hotbar_scale = (50 + 5) / 20.0
			self.hotbar_sprite.scale = self.hotbar_scale
			
			frame_img = pyglet.image.load("textures/hotbar_frame.png")
			frame_tex = frame_img.get_texture()
			gl.glBindTexture(frame_tex.target, frame_tex.id)
			gl.glTexParameteri(frame_tex.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
			gl.glBindTexture(frame_tex.target, 0)
			
			self.selector_sprite = pyglet.sprite.Sprite(frame_tex)
			self.selector_sprite.scale = self.hotbar_scale
			
			self.has_hotbar_texture = True
		except Exception as e:
			print(f"Failed to load hotbar textures: {e}")
			import traceback
			traceback.print_exc()
			self.has_hotbar_texture = False

			
		# Interaction
		self.cursor_item = None
		self.mouse_x = 0
		self.drag_mode = None # "LEFT" or "RIGHT"
		self.drag_slots = set()
		self.drag_start_item_count = 0
		self.cursor_start_drag_count = 0

	def on_resize(self, width, height):
		self.width = width
		self.height = height
		# Update label positions? They are updated every frame in draw for now to be safe with centering logic.
		# But 'draw' logic recalculates x, y.

	def draw(self):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		
		w, h = self.width, self.height
		if w == 0 or h == 0: return

		# Common Projection Matrix (Ortho)
		# Z range increased to avoid clipping 3D icons
		# near = -256, far = 256
		dist = 512.0
		z_scale = -2.0 / dist
		
		proj = [
			2/w, 0.0, 0.0, 0.0,
			0.0, 2/h, 0.0, 0.0,
			0.0, 0.0, z_scale, 0.0,
			-1.0, -1.0, 0.0, 1.0
		]
		proj_ptr = (gl.GLfloat * 16)(*proj)

		# 1. Draw 2D UI Backgrounds (Slots)
		self.shader.use()
		gl.glUniformMatrix4fv(self.proj_loc, 1, gl.GL_FALSE, proj_ptr)
		
		# self.draw_hotbar_bg() # Moved outside to support textured sprites
		if self.menu_open:
			self.draw_menu_bg()
		self.shader.stop()

		# Draw Hotbar Background (Textures or Fallback)
		# We draw this after stopping the simple shader because Sprites use their own state
		self.draw_hotbar_bg()


		# 2. Draw 3D Items (On top of slots)
		# Enable depth test for the cubes themselves so they sort correctly
		# Actually, we clear depth or just rely on painters algorithm?
		# Since they are individual convex cubes, we can just draw them.
		# But internal face sorting matters.
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glClear(gl.GL_DEPTH_BUFFER_BIT) # Clear so they draw on top of world
		
		self.icon_shader.use()
		gl.glUniformMatrix4fv(self.icon_proj_loc, 1, gl.GL_FALSE, proj_ptr)
		gl.glUniform1i(self.icon_tex_loc, 0) # Texture Unit 0
		
		# Bind Texture Array
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
		
		# Calculate positions for labels while drawing items
		self.update_hotbar_labels()
		
		if self.menu_open:
			# Update Title
			self.title_label.text = "Crafting" if self.inventory.crafting_size == 3 else "Inventory"
			self.title_label.x = self.width / 2
			self.title_label.y = self.height / 2 + 100
		else:
			self.title_label.text = ""

		self.draw_hotbar_items()
		if self.menu_open:
			self.draw_menu_items()
			
			# Draw Cursor Item if exists
			if self.cursor_item:
				mx, my = self.mouse_x, self.mouse_y
				self.draw_cube_icon(mx, my, 50, self.cursor_item.block_type)
			
		self.icon_shader.stop()
		
		gl.glDisable(gl.GL_BLEND)
		gl.glDisable(gl.GL_DEPTH_TEST)
		
		# 3. Draw Text Labels (Hotbar overlay)
		# Pyglet text drawing sets its own state (projection etc).
		# We're in 2D mode with depth disabled.
		self.label_batch.draw()
		
		# Draw Cursor Count
		if self.cursor_item and self.cursor_item.count > 1:
			# Should use a label, but for quick hack just skip or create temp label
			# Creating temp label every frame is bad. Maybe add to batch dynamically?
			# Ignoring cursor count text for this step to keep it simple, or add visual clutter.
			pass
		
		gl.glEnable(gl.GL_DEPTH_TEST) # Restore


	def on_mouse_motion(self, x, y, dx, dy):
		self.mouse_x = x
		self.mouse_y = y

	def get_slot_at(self, x, y):
		if not self.menu_open: return None, None
		
		center_x = self.width / 2
		center_y = self.height / 2
		slot_size, padding = 50, 5
		grid_w = (slot_size + padding) * 9
		start_x = center_x - grid_w / 2
		start_y = center_y
		
		# Main Inventory (3 rows)
		for row in range(3):
			for col in range(9):
				sx = start_x + col * (slot_size + padding)
				sy = start_y - row * (slot_size + padding)
				if sx <= x < sx + slot_size and sy <= y < sy + slot_size:
					return "main", row * 9 + col
					
		# Hotbar (in menu) - Usually strictly hotbar is shown separate at bottom, but often in menu it is bottom row.
		# My hotbar is handled by `draw_hotbar_bg` at bottom. Check that rect (similar logic).
		hb_w = (slot_size + padding) * 9
		hb_start_x = (self.width - hb_w) / 2
		hb_y = 20
		for i in range(9):
			sx = hb_start_x + i * (slot_size + padding)
			sy = hb_y
			if sx <= x < sx + slot_size and sy <= y < sy + slot_size:
				return "hotbar", i
				
		# Crafting Grid (2x2 or 3x3)
		size = self.inventory.crafting_size
		craft_y_start = start_y + (slot_size + padding) * 3.5
		craft_x_start = center_x - (slot_size + padding) * (size/2)
		for row in range(size):
			for col in range(size):
				sx = craft_x_start + col * (slot_size + padding)
				sy = craft_y_start - row * (slot_size + padding)
				if sx <= x < sx + slot_size and sy <= y < sy + slot_size:
					return "crafting", row * size + col
		
		# Output Slot
		arrow_x = craft_x_start + (slot_size + padding) * (size + 0.2)
		arrow_y = craft_y_start - (slot_size + padding) * (size / 2 - 0.5)
		out_x = arrow_x + 50
		out_y = arrow_y - (slot_size / 2) + 5
		if out_x <= x < out_x + slot_size and out_y <= y < out_y + slot_size:
			return "output", 0
			
		return None, None

	def on_mouse_press(self, x, y, button, modifiers):
		if not self.menu_open: return
		
		slot_type, index = self.get_slot_at(x, y)
		
		# Reset Drag
		self.drag_mode = None
		self.drag_slots = set()
		
		if not slot_type: 
			# Drop cursor item if clicked outside?
			return
		
		# Helper to get source list
		source_list = None
		if slot_type == "main": source_list = self.inventory.main_inventory
		elif slot_type == "hotbar": source_list = self.inventory.hotbar
		elif slot_type == "crafting": source_list = self.inventory.crafting_grid
		elif slot_type == "output": source_list = None 
		
		clicked_item = source_list[index] if source_list else None
		
		# SHIFT CLICK
		if modifiers & pyglet.window.key.MOD_SHIFT:
			if not clicked_item and slot_type != "output": return
			
			if slot_type == "output":
				# Craft Max Possible
				# Loop craft until result changes or inventory full
				# Simplified: Craft one stack limit or as much as fits
				# For now, just craft once for safety, or simple loop
				# If we craft once, we get item in mouse? No, Shift puts in inventory.
				
				# We check output
				if self.inventory.crafting_output:
					# Try to add to inventory
					# Consume ingredients
					# Repeat
					
					# Infinite loop guard
					for _ in range(64):
						if not self.inventory.crafting_output: break
						
						# Create temp item copy
						out_item = self.inventory.InventoryItem(self.inventory.crafting_output.block_type, self.inventory.crafting_output.count)
						
						rem = self.inventory.add_item(out_item)
						if rem == 0:
							# Success, consume ingredients
							self.inventory.craft()
						else:
							# Inventory full
							break
					
					self.inventory.update_crafting_output()
			
			else:
				# Move between Hotbar <-> Inventory
				item_to_move = clicked_item
				
				# Target list
				targets = []
				if slot_type == "hotbar": targets = [self.inventory.main_inventory]
				elif slot_type == "main": targets = [self.inventory.hotbar]
				elif slot_type == "crafting": targets = [self.inventory.main_inventory, self.inventory.hotbar]
				
				# Try move
				for target in targets:
					# Try stack
					for exist in target:
						if exist and exist.block_type == item_to_move.block_type:
							add = min(item_to_move.count, 64 - exist.count)
							if add > 0:
								exist.count += add
								item_to_move.count -= add
								if item_to_move.count == 0: break
					if item_to_move.count == 0: break
					
					# Try empty
					if item_to_move.count > 0:
						for i in range(len(target)):
							if target[i] is None:
								target[i] = self.inventory.InventoryItem(item_to_move.block_type, item_to_move.count)
								item_to_move.count = 0
								break
				
				if item_to_move.count == 0:
					source_list[index] = None
				
			# Update GUI
			if slot_type == "crafting": self.inventory.update_crafting_output()
			return

		# NORMAL CLICK
		
		# CLICK ON OUTPUT
		if slot_type == "output":
			if self.inventory.crafting_output:
				if not self.cursor_item:
					self.cursor_item = self.inventory.crafting_output
					self.inventory.craft() 
				elif self.cursor_item.block_type == self.inventory.crafting_output.block_type:
					self.cursor_item.count += self.inventory.crafting_output.count
					self.inventory.craft()
			return

		# CLICK ON SLOTS
		if not self.cursor_item:
			# Pick up
			if clicked_item:
				if button == pyglet.window.mouse.RIGHT:
					# Split (Half)
					half = clicked_item.count // 2 + (clicked_item.count % 2)
					leave = clicked_item.count - half
					
					self.cursor_item = self.inventory.InventoryItem(clicked_item.block_type, half)
					clicked_item.count = leave
					if clicked_item.count == 0: source_list[index] = None
				else:
					self.cursor_item = clicked_item
					source_list[index] = None
		else:
			# Place / Swap
			if not clicked_item:
				# Place
				if button == pyglet.window.mouse.RIGHT:
					# Place 1
					source_list[index] = inventory.InventoryItem(self.cursor_item.block_type, 1)
					self.cursor_item.count -= 1
					if self.cursor_item.count <= 0: self.cursor_item = None
				else:
					# Place All
					source_list[index] = self.cursor_item
					self.cursor_item = None
			else:
				# Swap or Add
				if clicked_item.block_type == self.cursor_item.block_type:
					# Add
					if button == pyglet.window.mouse.RIGHT:
						# Add 1
						clicked_item.count += 1
						self.cursor_item.count -= 1
						if self.cursor_item.count <= 0: self.cursor_item = None
					else:
						# Add All
						clicked_item.count += self.cursor_item.count
						self.cursor_item = None
				else:
					# Swap
					source_list[index] = self.cursor_item
					self.cursor_item = clicked_item
					
		# Update Crafting if needed
		if slot_type == "crafting":
			self.inventory.update_crafting_output()
			
		self.inventory.save() # Auto-save click

	def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
		if not self.menu_open: return
		
		# Update mouse pos for drawing
		self.mouse_x = x
		self.mouse_y = y
		
		slot_type, index = self.get_slot_at(x, y)
		if not slot_type or slot_type == "output": return
		
		# Identify source list
		source_list = None
		if slot_type == "main": source_list = self.inventory.main_inventory
		elif slot_type == "hotbar": source_list = self.inventory.hotbar
		elif slot_type == "crafting": source_list = self.inventory.crafting_grid
		
		# RIGHT DRAG (PAINT 1)
		if buttons & pyglet.window.mouse.RIGHT:
			if self.cursor_item and self.cursor_item.count > 0:
				# Unique ID for slot to prevent multi-place in same slot during one drag
				slot_id = f"{slot_type}_{index}"
				if slot_id not in self.drag_slots:
					# Try Place 1
					existing = source_list[index]
					if existing is None:
						source_list[index] = inventory.InventoryItem(self.cursor_item.block_type, 1)
						self.cursor_item.count -= 1
						self.drag_slots.add(slot_id)
					elif existing.block_type == self.cursor_item.block_type:
						existing.count += 1
						self.cursor_item.count -= 1
						self.drag_slots.add(slot_id)
					
					if self.cursor_item.count <= 0: self.cursor_item = None
					
					if slot_type == "crafting": self.inventory.update_crafting_output()
					
					self.inventory.save() # Auto-save drag
		
		# LEFT DRAG (Not implemented fully, just standard drag)

	def on_mouse_release(self, x, y, button, modifiers):
		self.drag_slots = set()
		self.drag_mode = None



	def update_hotbar_labels(self):
		slot_size = 50
		padding = 5
		total_w = (slot_size + padding) * 9
		start_x = (self.width - total_w) / 2
		y = 20
		
		for i in range(9):
			item = self.inventory.hotbar[i]
			label = self.hotbar_labels[i]
			
			x = start_x + i * (slot_size + padding)
			# Position text at bottom right of slot
			label.x = x + slot_size - 2
			label.y = y + 2
			
			if item and item.count > 1:
				label.text = str(item.count)
			else:
				label.text = ''


	# --- 2D Drawing Helpers ---

	def draw_rect(self, x, y, w, h, color):
		x1, y1 = x, y
		x2, y2 = x + w, y + h
		verts = [x1, y1, x2, y1, x1, y2, x1, y2, x2, y1, x2, y2]
		colors = list(color) * 6
		num_verts = 6
		vl = self.shader.vertex_list(num_verts, gl.GL_TRIANGLES, position=('f', verts), color=('f', colors))
		vl.draw(gl.GL_TRIANGLES)

	def draw_hotbar_bg(self):
		slot_size = 50
		padding = 5
		total_w = (slot_size + padding) * 9
		start_x = (self.width - total_w) / 2
		y = 20

		if getattr(self, 'has_hotbar_texture', False):
			# Draw Sprite
			# Center hotbar sprite
			sw = self.hotbar_sprite.width
			# Center of screen
			self.hotbar_sprite.x = self.width / 2 - sw / 2
			self.hotbar_sprite.y = y # Align bottom roughly with slot y
			
			# Adjust Y to align slots visually if needed. 
			# Slots in texture are likely 1px from bottom (scaled).
			# scale is ~2.75. So ~3px up?
			# Let's keep it simple at y=20 for now.
			
			self.hotbar_sprite.draw()
			
			# Selection Frame
			i = self.inventory.selected_hotbar_index
			# Calculate center of the logical slot
			slot_x = start_x + i * (slot_size + padding)
			slot_y = y
			
			cx = slot_x + slot_size / 2
			cy = slot_y + slot_size / 2
			
			# Center the frame sprite on the slot center
			fw = self.selector_sprite.width
			fh = self.selector_sprite.height
			
			# User adjustment: 1px right and 1px up
			self.selector_sprite.x = (cx - fw / 2) + 3
			self.selector_sprite.y = (cy - fh / 2) + 3
			self.selector_sprite.draw()
			
		else:
			# Fallback to Rects (Requires Shader Setup)
			self.shader.use()
			
			# Setup Projection (Output of calculation from draw())
			w, h = self.width, self.height
			dist = 512.0
			z_scale = -2.0 / dist
			proj = [
				2/w, 0.0, 0.0, 0.0,
				0.0, 2/h, 0.0, 0.0,
				0.0, 0.0, z_scale, 0.0,
				-1.0, -1.0, 0.0, 1.0
			]
			proj_ptr = (gl.GLfloat * 16)(*proj)
			gl.glUniformMatrix4fv(self.proj_loc, 1, gl.GL_FALSE, proj_ptr)
			
			# Background Panel
			self.draw_rect(start_x - 10, y - 10, total_w + 10, slot_size + 20, (0, 0, 0, 0.5))
			
			for i in range(9):
				x = start_x + i * (slot_size + padding)
				
				# Highlight (Border)
				if i == self.inventory.selected_hotbar_index:
					# Draw white border (slightly larger box behind)
					self.draw_rect(x - 2, y - 2, slot_size + 4, slot_size + 4, (1.0, 1.0, 1.0, 1.0))
				
				# Slot BG
				color = (0.3, 0.3, 0.3, 0.8)
				self.draw_rect(x, y, slot_size, slot_size, color)
				
			self.shader.stop()

	def draw_menu_bg(self):
		self.draw_rect(0, 0, self.width, self.height, (0, 0, 0, 0.7))
		
		center_x = self.width / 2
		center_y = self.height / 2
		slot_size, padding = 50, 5
		grid_w = (slot_size + padding) * 9
		start_x = center_x - grid_w / 2
		start_y = center_y
		
		# 3 Rows of Main Inventory
		for row in range(3):
			for col in range(9):
				x = start_x + col * (slot_size + padding)
				y = start_y - row * (slot_size + padding)
				self.draw_rect(x, y, slot_size, slot_size, (0.4, 0.4, 0.4, 0.9))
				
		# Crafting Area (2x2 or 3x3)
		size = self.inventory.crafting_size
		craft_y_start = start_y + (slot_size + padding) * 3.5
		craft_x_start = center_x - (slot_size + padding) * (size / 2)
		
		# Grid
		for row in range(size):
			for col in range(size):
				x = craft_x_start + col * (slot_size + padding)
				y = craft_y_start - row * (slot_size + padding)
				self.draw_rect(x, y, slot_size, slot_size, (0.5, 0.5, 0.5, 0.9))
		
		# Arrow (Simple Rect for now)
		arrow_x = craft_x_start + (slot_size + padding) * 2.2
		arrow_y = craft_y_start - (slot_size + padding) * 0.5
		self.draw_rect(arrow_x, arrow_y, 40, 10, (0.7, 0.7, 0.7, 1.0))
		
		# Output Slot
		out_x = arrow_x + 50
		out_y = arrow_y - (slot_size / 2) + 5
		self.draw_rect(out_x, out_y, slot_size, slot_size, (0.5, 0.5, 0.5, 0.9))

	# --- 3D Drawing Helpers ---

	def draw_cube_icon(self, x, y, size, block_type_id):
		if not block_type_id: return
		if block_type_id >= len(self.world.block_types): return
		block = self.world.block_types[block_type_id]
		if not block: return

		# Setup Model Matrix
		cx = x + size / 2
		cy = y + size / 2
		
		m = matrix.Matrix()
		m.load_identity()
		m.translate(cx, cy, 0)
		
		# Standard Isometric Rotation
		m.rotate(math.radians(20), 1, 0, 0) 
		m.rotate(math.radians(45), 0, 1, 0)
		
		if block.is_sprite:
			m.scale(size * 0.5, size * 0.5, size * 0.5)
		else:
			m.scale(size * 0.35, size * 0.35, size * 0.35) 

		# Flatten matrix
		flat_matrix = []
		for i in range(4):
			for j in range(4):
				flat_matrix.append(m.data[i][j])
		
		gl.glUniformMatrix4fv(self.icon_model_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_matrix))
		
		data = []
		num_verts = 0

		if block.is_sprite:
			# Use ItemModel for 3D item icon
			sprite_path = block.sprite_path
			if not hasattr(self, "item_model_cache"): self.item_model_cache = {}
			if sprite_path not in self.item_model_cache:
				import item_model
				self.item_model_cache[sprite_path] = item_model.ItemModel(sprite_path)
			
			gen = self.item_model_cache[sprite_path]
			vertices, tex, shades, inds = gen.generate_mesh(texture_index=block.sprite_index)
			
			# We need to emit Triangles (inds)
			# vertices: [v1x, v1y, v1z, v2x, ...]
			# tex: [u1, v1, w1, ...]
			# shades: [s1, s2, ...]
			# indices: [i1, i2, i3, i4, i5, i6, ...]
			
			# Prepare interleaved data for the triangle list
			# Actually, we can just use DrawElements if we had a temporary buffer.
			# But vertex_list doesn't support indices easily in this way.
			# Let's just flat out the triangle data.
			for idx in inds:
				# Pos
				data.extend(vertices[idx*3 : idx*3+3])
				# Tex
				data.extend(tex[idx*3 : idx*3+3])
				# Shade
				data.append(shades[idx])
			
			num_verts = len(inds)

		else:
			# Cube data
			x1, y1, z1 = -0.5, -0.5, -0.5
			x2, y2, z2 =  0.5,  0.5,  0.5
			
			def face(coords, uvs, shade):
				v = []
				# Tri 1: 0,1,2
				v.extend(coords[0]); v.extend(uvs[0]); v.append(shade)
				v.extend(coords[1]); v.extend(uvs[1]); v.append(shade)
				v.extend(coords[2]); v.extend(uvs[2]); v.append(shade)
				# Tri 2: 0,2,3
				v.extend(coords[0]); v.extend(uvs[0]); v.append(shade)
				v.extend(coords[2]); v.extend(uvs[2]); v.append(shade)
				v.extend(coords[3]); v.extend(uvs[3]); v.append(shade)
				return v

			def get_face_uvs(face_index):
				f_idx = face_index if face_index < len(block.tex_coords) else 0
				fl = block.tex_coords[f_idx]
				return [(fl[0], fl[1], fl[2]), (fl[3], fl[4], fl[5]), (fl[6], fl[7], fl[8]), (fl[9], fl[10], fl[11])]

			data.extend(face([(x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1)], get_face_uvs(2), 1.0)) # Top
			data.extend(face([(x1,y1,z2), (x2,y1,z2), (x2,y1,z1), (x1,y1,z1)], get_face_uvs(3), 0.5)) # Bottom
			data.extend(face([(x2,y2,z2), (x2,y1,z2), (x2,y1,z1), (x2,y2,z1)], get_face_uvs(0), 0.6)) # Right
			data.extend(face([(x1,y2,z1), (x1,y1,z1), (x1,y1,z2), (x1,y2,z2)], get_face_uvs(1), 0.6)) # Left
			data.extend(face([(x1,y2,z2), (x1,y1,z2), (x2,y1,z2), (x2,y2,z2)], get_face_uvs(4), 0.8)) # Front
			data.extend(face([(x2,y2,z1), (x2,y1,z1), (x1,y1,z1), (x1,y2,z1)], get_face_uvs(5), 0.8)) # Back
			
			num_verts = len(data) // 7

		# Draw
		pos_data = []
		os_tex_data = []
		shade_data = []
		
		for i in range(num_verts):
			base = i * 7
			pos_data.extend(data[base:base+3])
			os_tex_data.extend(data[base+3:base+6])
			shade_data.append(data[base+6])
			
		vl = self.icon_shader.vertex_list(num_verts, gl.GL_TRIANGLES,
			position=('f', pos_data),
			tex_coords=('f', os_tex_data),
			shading=('f', shade_data)
		)
		vl.draw(gl.GL_TRIANGLES)

	def draw_hotbar_items(self):
		slot_size = 50
		padding = 5
		total_w = (slot_size + padding) * 9
		start_x = (self.width - total_w) / 2
		y = 20
		
		for i in range(9):
			x = start_x + i * (slot_size + padding)
			item = self.inventory.hotbar[i]
			if item:
				self.draw_cube_icon(x, y, slot_size, item.block_type)

	def draw_menu_items(self):
		center_x = self.width / 2
		center_y = self.height / 2
		slot_size, padding = 50, 5
		grid_w = (slot_size + padding) * 9
		start_x = center_x - grid_w / 2
		start_y = center_y
		
		# Main Inventory
		for row in range(3):
			for col in range(9):
				index = row * 9 + col
				item = self.inventory.main_inventory[index]
				if item:
					x = start_x + col * (slot_size + padding)
					y = start_y - row * (slot_size + padding)
					self.draw_cube_icon(x, y, slot_size, item.block_type)

		# Crafting Items
		self.draw_crafting_items()

	def draw_crafting_items(self):
		center_x = self.width / 2
		center_y = self.height / 2
		slot_size, padding = 50, 5
		start_y = center_y
		
		size = self.inventory.crafting_size
		craft_y_start = start_y + (slot_size + padding) * 3.5
		craft_x_start = center_x - (slot_size + padding) * (size / 2)
		
		# Grid
		for row in range(size):
			for col in range(size):
				index = row * size + col
				item = self.inventory.crafting_grid[index]
				if item:
					x = craft_x_start + col * (slot_size + padding)
					y = craft_y_start - row * (slot_size + padding)
					self.draw_cube_icon(x, y, slot_size, item.block_type)
		
		# Output Item
		arrow_x = craft_x_start + (slot_size + padding) * (size + 0.2)
		arrow_y = craft_y_start - (slot_size + padding) * (size / 2 - 0.5)
		out_x = arrow_x + 50
		out_y = arrow_y - (slot_size / 2) + 5
		
		if self.inventory.crafting_output:
			self.draw_cube_icon(out_x, out_y, slot_size, self.inventory.crafting_output.block_type)
