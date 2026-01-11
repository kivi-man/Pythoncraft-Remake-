import pyglet
from pyglet import gl
import math
import json
import os
import ctypes

# Import project modules
import matrix
import mob
import block_type
import world
import texture_manager
import item_model

import models.cube
import models.torch
import models.stairs
import models.plant
import models.leaves
import models.glass
import models.slab
import models.flat
import models.crop
import models.soil
import models.sign_post
import models.door
import models.ladder
import models.sign
import models.lever
import models.pressure_plate
import models.button
import models.cactus

# Mini Shader for the GUI
vertex_source = """#version 330
layout(location = 0) in vec3 position;
layout(location = 1) in vec3 tex_coords;
layout(location = 2) in float shading;

out vec3 v_tex_coords;
out float v_shading;

uniform mat4 matrix;

void main()
{
    gl_Position = matrix * vec4(position, 1.0);
    v_tex_coords = tex_coords;
    v_shading = shading;
}
"""

fragment_source = """#version 330
in vec3 v_tex_coords;
in float v_shading;
out vec4 out_color;

uniform sampler2DArray texture_array;

void main()
{
    out_color = texture(texture_array, v_tex_coords);
    out_color.rgb *= v_shading;
}
"""

class ItemGUI(pyglet.window.Window):
    def __init__(self):
        super().__init__(width=800, height=600, caption="Item Hand Transform Tool", resizable=True)
        
        # Initialize basic world systems
        self.texture_manager = texture_manager.Texture_manager(16, 16, 256)
        self.world = FakeWorld(self.texture_manager)
        
        # Load Shader
        self.shader = pyglet.graphics.shader.ShaderProgram(
            pyglet.graphics.shader.Shader(vertex_source, 'vertex'),
            pyglet.graphics.shader.Shader(fragment_source, 'fragment')
        )
        self.matrix_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'matrix'))
        
        # Steve
        self.steve = mob.Mob(self.world, (0, 0, 0))
        self.steve.rotation = [0, 0, 0]
        
        # Tool state
        self.mode = "TPS" # or "FPS"
        self.current_item_id = 270 # Start with Wooden Pickaxe (Sprite)
        self.available_items = [i for i, b in enumerate(self.world.block_types) if b is not None]
        self.sprite_items = [i for i, b in enumerate(self.world.block_types) if b is not None and b.is_sprite]
        self.item_idx = self.available_items.index(self.current_item_id) if self.current_item_id in self.available_items else 0
        
        self.transforms = {}
        self.load_settings()
        
        # Geometry for hand item
        self.item_vao = gl.GLuint(0)
        self.item_vbo = gl.GLuint(0)
        self.item_ibo = gl.GLuint(0)
        self.item_vertex_count = 0
        gl.glGenVertexArrays(1, self.item_vao)
        gl.glGenBuffers(1, self.item_vbo)
        gl.glGenBuffers(1, self.item_ibo)
        
        self.item_model_cache = {}
        
        self.update_item_mesh()
        
        # Camera
        self.camera_rot = [0, 0]
        self.camera_dist = 3.0
        
        pyglet.clock.schedule_interval(self.update, 1/60.0)
        
        self.label = pyglet.text.Label(
            '', font_name='Arial', font_size=10, 
            x=10, y=self.height-10, anchor_y='top', 
            multiline=True, width=1200
        )

        self.save_message_label = pyglet.text.Label(
            'SETTINGS SAVED', font_name='Arial', font_size=24,
            x=self.width/2, y=self.height/2, anchor_x='center', anchor_y='center',
            color=(0, 255, 0, 255)
        )
        self.save_message_timer = 0.0

        # Input Handler
        self.keys = pyglet.window.key.KeyStateHandler()
        self.push_handlers(self.keys)

    def load_settings(self):
        if os.path.exists("data/item_transforms.json"):
            with open("data/item_transforms.json", "r") as f:
                self.transforms = json.load(f)
        
    def save_settings(self):
        os.makedirs("data", exist_ok=True)
        with open("data/item_transforms.json", "w") as f:
            json.dump(self.transforms, f, indent=4)
        print("Settings saved to data/item_transforms.json")
        self.save_message_timer = 2.0

    def get_current_settings(self):
        sid = str(self.current_item_id)
        if sid not in self.transforms:
            self.transforms[sid] = {
                "FPS": {"pos": [0.6, -0.6, -1.2], "rot": [0, -45, 0], "scale": [0.6, 0.6, 0.6]},
                "TPS": {"pos": [0.3, -1.0, 0.15], "rot": [0, 45, 0], "scale": [0.25, 0.25, 0.25]}
            }
        return self.transforms[sid][self.mode]

    def update_item_mesh(self):
        block_type = self.world.block_types[self.current_item_id]
        if not block_type: return

        data = []
        indices = []
        index_offset = 0

        if block_type.is_sprite:
            sprite_path = block_type.sprite_path
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
            # Simple Cube
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

        self.item_vertex_count = len(indices)

        gl.glBindVertexArray(self.item_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.item_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, len(data) * 4, (gl.GLfloat * len(data))(*data), gl.GL_STATIC_DRAW)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.item_ibo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, len(indices) * 4, (gl.GLuint * len(indices))(*indices), gl.GL_STATIC_DRAW)
        
        stride = 7 * 4
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 24)
        gl.glEnableVertexAttribArray(2)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons & pyglet.window.mouse.LEFT:
            self.camera_rot[0] += dx * 0.5
            self.camera_rot[1] -= dy * 0.5
        elif buttons & pyglet.window.mouse.RIGHT:
            s = self.get_current_settings()
            s["rot"][1] += dx * 0.5
            s["rot"][0] -= dy * 0.5
            
    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera_dist -= scroll_y * 0.5
        self.camera_dist = max(1.0, self.camera_dist)

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.LEFT:
            self.item_idx = (self.item_idx - 1) % len(self.available_items)
            self.current_item_id = self.available_items[self.item_idx]
            self.update_item_mesh()
        elif symbol == pyglet.window.key.RIGHT:
            self.item_idx = (self.item_idx + 1) % len(self.available_items)
            self.current_item_id = self.available_items[self.item_idx]
            self.update_item_mesh()
        elif symbol == pyglet.window.key.UP:
            if self.sprite_items:
                # Find current index in sprites or default 0
                curr = self.current_item_id if self.current_item_id in self.sprite_items else self.sprite_items[0]
                idx = self.sprite_items.index(curr)
                self.current_item_id = self.sprite_items[(idx + 1) % len(self.sprite_items)]
                self.update_item_mesh()
        elif symbol == pyglet.window.key.DOWN:
            if self.sprite_items:
                curr = self.current_item_id if self.current_item_id in self.sprite_items else self.sprite_items[0]
                idx = self.sprite_items.index(curr)
                self.current_item_id = self.sprite_items[(idx - 1) % len(self.sprite_items)]
                self.update_item_mesh()
        elif symbol == pyglet.window.key.TAB:
            self.mode = "FPS" if self.mode == "TPS" else "TPS"
        elif symbol == pyglet.window.key.ENTER:
            self.save_settings()

    def update_input(self, dt):
        s = self.get_current_settings()
        
        mult = 5.0 if self.keys[pyglet.window.key.LSHIFT] else 1.0
        speed = 0.5 * dt * mult
        rot_speed = 50 * dt * mult
        
        # Position
        if self.keys[pyglet.window.key.T]: s["pos"][0] += speed
        if self.keys[pyglet.window.key.G]: s["pos"][0] -= speed
        if self.keys[pyglet.window.key.Y]: s["pos"][1] += speed
        if self.keys[pyglet.window.key.H]: s["pos"][1] -= speed
        if self.keys[pyglet.window.key.U]: s["pos"][2] += speed
        if self.keys[pyglet.window.key.J]: s["pos"][2] -= speed
        
        # Rotation
        if self.keys[pyglet.window.key.R]: s["rot"][0] += rot_speed
        if self.keys[pyglet.window.key.F]: s["rot"][0] -= rot_speed
        if self.keys[pyglet.window.key.O]: s["rot"][1] += rot_speed
        if self.keys[pyglet.window.key.P]: s["rot"][1] -= rot_speed
        if self.keys[pyglet.window.key.K]: s["rot"][2] += rot_speed
        if self.keys[pyglet.window.key.L]: s["rot"][2] -= rot_speed
        
        # Scale
        if self.keys[pyglet.window.key.M]: 
            s["scale"][0] += speed; s["scale"][1] += speed; s["scale"][2] += speed
        if self.keys[pyglet.window.key.N]: 
            s["scale"][0] -= speed; s["scale"][1] -= speed; s["scale"][2] -= speed

    def update(self, dt):
        self.update_input(dt)
        if self.save_message_timer > 0:
            self.save_message_timer -= dt
        
        s = self.get_current_settings()
        item_name = self.world.block_types[self.current_item_id].name
        
        # Round format for cleaner display
        def fmt(lst): return f"[{lst[0]:.2f}, {lst[1]:.2f}, {lst[2]:.2f}]"
        
        self.label.text = f"Item: {item_name} (ID: {self.current_item_id})\nMode: {self.mode}\nPos: {fmt(s['pos'])}\nRot: {fmt(s['rot'])}\nScale: {fmt(s['scale'])}\n\nControls:\nLeft Drag: Camera | Right Drag: Rotate Item\nShift: Speed Up\nT/G: X pos, Y/H: Y pos, U/J: Z pos\nR/F: X rot, O/P: Y rot, K/L: Z rot\nM/N: Scale\nARROWS: Change Item/Sprite | TAB: Mode | ENTER: Save"

    def on_draw(self):
        self.clear()
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        
        # Projection
        aspect = self.width / self.height
        p = matrix.Matrix()
        p.load_identity()
        p.perspective(90, aspect, 0.1, 100.0)
        
        # View
        v = matrix.Matrix()
        v.load_identity()
        if self.mode == "TPS":
            v.translate(0, -1, -self.camera_dist)
            v.rotate(math.radians(20 + self.camera_rot[1]), 1, 0, 0)
            v.rotate(math.radians(self.camera_rot[0]), 0, 1, 0)
        else:
            # FPS View - Camera at eye level
            v.rotate(math.radians(self.camera_rot[1]), 1, 0, 0)
            v.rotate(math.radians(self.camera_rot[0]), 0, 1, 0)
            
        # Draw Steve (only in TPS)
        if self.mode == "TPS":
            self.steve.draw(p, v)
        
        # Draw Item
        s = self.get_current_settings()
        m_item = matrix.Matrix()
        m_item.load_identity()
        
        if self.mode == "TPS":
            # Parent to right arm
            ps = 0.06
            m_item.translate(*self.steve.position)
            m_item.rotate_2d(-self.steve.rotation[0] - math.pi, 0)
            # Arm transform
            m_arm = matrix.Matrix()
            m_arm.load_identity()
            m_arm.translate(6*ps, 24*ps, 0)
            # ... we'd need to match mob.py arm rotation logic ...
            m_item = p * v * m_item * m_arm
        else:
            # FPS View
            m_item.load_identity()
            m_item = p * m_item # Screen space roughly
            
        m_final = matrix.Matrix()
        m_final.load_identity()
        m_final.translate(*s["pos"])
        m_final.rotate(math.radians(s["rot"][0]), 1, 0, 0)
        m_final.rotate(math.radians(s["rot"][1]), 0, 1, 0)
        m_final.rotate(math.radians(s["rot"][2]), 0, 0, 1)
        m_final.scale(*s["scale"])
        m_final.translate(-0.5, -0.5, -0.5) # Center model
        
        final_mvp = m_item * m_final
        
        self.shader.use()
        flat_mvp = []
        for i in range(4):
            for j in range(4):
                flat_mvp.append(final_mvp.data[i][j])
        gl.glUniformMatrix4fv(self.matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_mvp))
        
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.texture_manager.texture_array)
        
        gl.glBindVertexArray(self.item_vao)
        gl.glDrawElements(gl.GL_TRIANGLES, self.item_vertex_count, gl.GL_UNSIGNED_INT, None)
        
        gl.glDisable(gl.GL_DEPTH_TEST)
        self.label.draw()
        if self.save_message_timer > 0:
            self.save_message_label.draw()
        gl.glEnable(gl.GL_DEPTH_TEST)

class FakeWorld:
    def __init__(self, texture_manager):
        self.texture_manager = texture_manager
        self.block_types = [None] * 500
        self.load_blocks()
        
    def load_blocks(self):
        # Mini parser for blocks.mcpy
        with open("data/blocks.mcpy", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = line.split(": ", 1)
                idx = int(parts[0])
                props = parts[1].split(", ")
                
                name = ""
                is_sprite = False
                sprite_path = ""
                
                if props:
                    for p in props:
                        if p.startswith("name"): name = eval(p.split("name ")[1])
                        if p.startswith("sprite"): 
                            is_sprite = True
                            sprite_path = eval(p.split("sprite ")[1])
                        if p.startswith("model"): 
                            model_str = p.split("model ")[1]
                            if model_str == "models.cube": model_obj = models.cube
                            elif model_str == "models.torch": model_obj = models.torch
                            elif model_str == "models.stairs": model_obj = models.stairs
                            elif model_str == "models.plant": model_obj = models.plant
                            elif model_str == "models.leaves": model_obj = models.leaves
                            elif model_str == "models.glass": model_obj = models.glass
                            elif model_str == "models.slab": model_obj = models.slab
                            elif model_str == "models.flat": model_obj = models.flat
                            elif model_str == "models.crop": model_obj = models.crop
                            elif model_str == "models.soil": model_obj = models.soil
                            elif model_str == "models.sign_post": model_obj = models.sign_post
                            elif model_str == "models.door": model_obj = models.door
                            elif model_str == "models.ladder": model_obj = models.ladder
                            elif model_str == "models.sign": model_obj = models.sign
                            elif model_str == "models.lever": model_obj = models.lever
                            elif model_str == "models.pressure_plate": model_obj = models.pressure_plate
                            elif model_str == "models.button": model_obj = models.button
                            elif model_str == "models.cactus": model_obj = models.cactus
                            else: model_obj = models.cube # Fallback
                        else:
                            model_obj = models.cube
                
                bt = block_type.Block_type(self.texture_manager, name, {}, model_obj, 1.0, "stone", is_sprite, sprite_path)
                if is_sprite:
                    tex_name = sprite_path.replace("textures/", "").replace(".png", "")
                    self.texture_manager.add_texture(tex_name)
                    bt.sprite_index = self.texture_manager.textures.index(tex_name)
                
                self.block_types[idx] = bt
        self.texture_manager.generate_mipmaps()

    def get_block_number(self, pos): return 0

if __name__ == "__main__":
    app = ItemGUI()
    pyglet.app.run()
