import math
import random
import pyglet
from pyglet import gl
import entity
import matrix
import ctypes

vertex_source = """#version 330
layout(location = 0) in vec3 position;
layout(location = 1) in vec2 tex_coords;
layout(location = 2) in float shading;

out vec2 v_tex_coords;
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
in vec2 v_tex_coords;
in float v_shading;
out vec4 out_color;

uniform sampler2D texture_sampler;

// Simple red flash logic. 
// Ideally we pass uniform float hurt_intensity; but we used glColor4f in draw loop.
// Does basic shader support glColor? No, we didn't add "in vec4 color" from vertex.
// To support glColor, we need to pass it from vertex.
// BUT, pyglet.graphics.shader doesn't auto-bind glColor to attributes unless we specify.
// EASIER: Just use a uniform for hurt.

uniform float hurt_intensity; 

void main()
{
    vec4 tex_color = texture(texture_sampler, v_tex_coords);
    if(tex_color.a < 0.1) discard;
    
    vec3 mixed_color = mix(tex_color.rgb * v_shading, vec3(1.0, 0.0, 0.0), hurt_intensity);
    out_color = vec4(mixed_color, tex_color.a);
}
"""

class ModelPart:
    def __init__(self, texture_width, texture_height, uv_x, uv_y, size_x, size_y, size_z, origin_offset=(0,0,0)):
        self.uv_x = uv_x
        self.uv_y = uv_y
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z
        self.origin_offset = origin_offset
        self.rotation = [0, 0, 0]
        self.position = [0, 0, 0]
        self.vertex_count = 0
        self.vao = None
        self.vbo = None
        self._build_mesh(texture_width, texture_height)
        
    def _build_mesh(self, tw, th):
        pass

    def draw(self, parent_mv, shader_matrix_loc):
        m = matrix.Matrix()
        local = matrix.Matrix()
        local.load_identity()
        local.translate(*self.position)
        if self.rotation[0] != 0: local.rotate(self.rotation[0], 1, 0, 0)
        if self.rotation[1] != 0: local.rotate(self.rotation[1], 0, 1, 0)
        if self.rotation[2] != 0: local.rotate(self.rotation[2], 0, 0, 1)
        final = parent_mv * local
        flat_mvp = []
        for i in range(4):
            for j in range(4):
                flat_mvp.append(final.data[i][j])
        gl.glUniformMatrix4fv(shader_matrix_loc, 1, gl.GL_FALSE, (gl.GLfloat * 16)(*flat_mvp))
        gl.glBindVertexArray(self.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, self.vertex_count)

class Mob(entity.Entity):
    def __init__(self, world, position=(0, 0, 0)):
        super().__init__(world)
        self.position = list(position)
        self.gravity_enabled = True
        self.ai_timer = 0.0
        self.ai_state = 'idle'
        self.target_yaw = 0.0 # Body Target
        self.dest_yaw = 0.0   # Final Destination Yaw
        
        self.texture = None
        self.shader = None
        self._init_gl()
        self.parts = []
        self._build_steve()
        self.animation_state = None
        self.anim_time = 0.0

    def _init_gl(self):
        try:
            self.shader = pyglet.graphics.shader.ShaderProgram(
                pyglet.graphics.shader.Shader(vertex_source, 'vertex'),
                pyglet.graphics.shader.Shader(fragment_source, 'fragment')
            )
            self.matrix_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'matrix'))
            self.tex_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'texture_sampler'))
            self.hurt_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'hurt_intensity'))
            
            img = pyglet.image.load("textures/steve.png")
            self.texture = img.get_texture()
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        except Exception as e:
            print(f"Mob Init Error: {e}")


    def _build_steve(self):
        ps = 0.06
        self.head = ModelPart(64, 64, 0, 0, 8, 8, 8)
        self.head._build_mesh_custom(0, 0, 8, 8, 8, ps, pivot="bottom")
        self.head.position = [0, 24*ps, 0]
        self.body = ModelPart(64, 64, 16, 16, 8, 12, 4)
        self.body._build_mesh_custom(16, 16, 8, 12, 4, ps, pivot="top")
        self.body.position = [0, 24*ps, 0]
        self.r_arm = ModelPart(64, 64, 40, 16, 4, 12, 4)
        self.r_arm._build_mesh_custom(40, 16, 4, 12, 4, ps, pivot="top")
        self.r_arm.position = [6*ps, 24*ps, 0]
        self.l_arm = ModelPart(64, 64, 32, 48, 4, 12, 4)
        self.l_arm._build_mesh_custom(32, 48, 4, 12, 4, ps, pivot="top")
        self.l_arm.position = [-6*ps, 24*ps, 0]
        self.r_leg = ModelPart(64, 64, 0, 16, 4, 12, 4)
        self.r_leg._build_mesh_custom(0, 16, 4, 12, 4, ps, pivot="top")
        self.r_leg.position = [2*ps, 12*ps, 0]
        self.l_leg = ModelPart(64, 64, 16, 48, 4, 12, 4)
        self.l_leg._build_mesh_custom(16, 48, 4, 12, 4, ps, pivot="top")
        self.l_leg.position = [-2*ps, 12*ps, 0]
        self.parts = [self.head, self.body, self.r_arm, self.l_arm, self.r_leg, self.l_leg]

    def update(self, delta_time):
        self.ai_timer -= delta_time
        
        # --- State Machine Trigger ---
        if self.ai_timer <= 0:
            self.ai_timer = random.uniform(2.0, 5.0)
            if random.random() < 0.7:
                # Initiate Walk Sequence: Look -> Turn -> Walk
                self.ai_state = 'pre_walk_look'
                self.dest_yaw = random.choice([0, math.pi/2, math.pi, -math.pi/2])
                # Keep target_yaw same as current to freeze body
                self.target_yaw = self.target_yaw # No change
            else:
                self.ai_state = 'idle'
        
        # --- State Handlers ---
        
        # 1. Look at target (Head only)
        if self.ai_state == 'pre_walk_look':
            current_body = self.rotation[0]
            # Angle head should be at relative to body
            # Head Abs = Dest. Body Abs = Curr. Head Rel = Dest - Curr.
            # Normalization needed? 
            # If Dest=Pi, Curr=0, Rel=Pi.
            # Shortest path logic for head?
            
            # Simple absolute diff
            wanted_head_rel = (self.dest_yaw - current_body + math.pi) % (math.pi * 2) - math.pi
            
            # Smoothly rotate head to wanted_head_rel
            # Current head
            curr_h = self.head.rotation[1]
            diff = (wanted_head_rel - curr_h + math.pi) % (math.pi*2) - math.pi
            
            # Head turns fast
            h_speed = 8.0 * delta_time
            if abs(diff) < h_speed:
                self.head.rotation[1] = wanted_head_rel
                # Head Aligned! Next State.
                self.ai_state = 'pre_walk_turn'
                self.target_yaw = self.dest_yaw # NOW body starts turning
            else:
                self.head.rotation[1] += math.copysign(h_speed, diff)

        # 2. Turn Body (Head stays locked on target)
        elif self.ai_state == 'pre_walk_turn':
            # Body smooth rotation is handled below by self.target_yaw logic
            
            # We need to rotate Head BACK to 0 as Body turns to Target
            # effectively keeping Head Absolute Rotation constant.
            
            # Current Body is approaching Dest.
            # Head Rel should approach 0.
            target_h = 0.0
            curr_h = self.head.rotation[1]
            diff = (target_h - curr_h + math.pi) % (math.pi*2) - math.pi
             # Sync head speed with body speed roughly, or just interp fast?
            h_speed = 4.0 * delta_time
            if abs(diff) < h_speed:
                self.head.rotation[1] = target_h
            else:
                self.head.rotation[1] += math.copysign(h_speed, diff)

            # Check if Body is aligned
            curr_b = self.rotation[0]
            dist = abs((self.target_yaw - curr_b + math.pi) % (math.pi*2) - math.pi)
            if dist < 0.05:
                # Aligned!
                self.ai_state = 'walk'

        elif self.ai_state == 'idle':
            # Random Head Look
            target_h = math.sin(pyglet.clock.get_default().time() * 0.5) * 0.5
            # self.head.rotation[1] ... lerp to target_h
            # Simplified:
            self.head.rotation[1] = target_h

        # Body Smooth Rotation (Always Active for 'target_yaw')
        current_yaw = self.rotation[0]
        diff = (self.target_yaw - current_yaw + math.pi) % (math.pi * 2) - math.pi
        rot_speed = 4.0 * delta_time
        if abs(diff) < rot_speed:
            self.rotation[0] = self.target_yaw
        else:
            self.rotation[0] += math.copysign(rot_speed, diff)

        # 3. Walk Physics
        if self.ai_state == 'walk':
            # Orientation is aligned now.
            speed = 2.0
            dx = -math.sin(-self.rotation[0]) * speed
            dz = -math.cos(-self.rotation[0]) * speed
            
            # Safety Check
            check_dist = 0.6
            cx = self.position[0] - math.sin(-self.rotation[0]) * check_dist
            cz = self.position[2] - math.cos(-self.rotation[0]) * check_dist
            cy = self.position[1]
            
            if self.is_position_safe(cx, cy, cz):
                self.accel[0] = dx
                self.accel[2] = dz
            else:
                self.velocity = [0, self.velocity[1], 0]
                self.ai_state = 'idle'
            
            horz_speed = math.sqrt(self.velocity[0]**2 + self.velocity[2]**2)
            if self.grounded and horz_speed < 0.1:
                self.jump()

        super().update(delta_time)
        if self.hurt_timer > 0:
            self.hurt_timer -= delta_time
        
        # Animation Logic
        speed_horz = math.sqrt(self.velocity[0]**2 + self.velocity[2]**2)
        if speed_horz > 0.1 and self.ai_state == 'walk':
            self.animation_state = 'walk'
        else:
            self.animation_state = None

        if self.animation_state == 'walk':
            self.anim_time += delta_time * 10
            angle = math.sin(self.anim_time) * 0.6
            self.r_arm.rotation[0] = angle
            self.l_arm.rotation[0] = -angle
            self.r_leg.rotation[0] = -angle
            self.l_leg.rotation[0] = angle
        else:
            self.l_leg.rotation[0] *= 0.8

class Pig(Mob):
    def __init__(self, world, position=(0, 0, 0)):
        super().__init__(world, position)
        
    def _init_gl(self):
        try:
            self.shader = pyglet.graphics.shader.ShaderProgram(
                pyglet.graphics.shader.Shader(vertex_source, 'vertex'),
                pyglet.graphics.shader.Shader(fragment_source, 'fragment')
            )
            self.matrix_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'matrix'))
            self.tex_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'texture_sampler'))
            self.hurt_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'hurt_intensity'))
            
            # Load Pig Texture
            img = pyglet.image.load("textures/pig.png")
            self.texture = img.get_texture()
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        except Exception as e:
            print(f"Pig Init Error: {e}")

    def _build_steve(self):
        # Override to build Pig Model
        # Pig dimensions:
        # Head: 8x8x8
        # Body: 10x16x8 (Rotated 90 deg usually) -> Let's say 10 wide, 8 high, 16 long?
        # Minecraft Pig:
        # Head: 8x8x8
        # Body: 10w x 16L x 8H ? No, Body is usually rotated.
        # Let's approximate:
        # Body: 10 wide, 8 high, 16 long. (centered)
        # Legs: 4x6x4
        
        ps = 0.06
        
        # HEAD
        self.head = ModelPart(64, 32, 0, 0, 8, 8, 8)
        self.head._build_mesh_custom(0, 0, 8, 8, 8, ps, pivot="bottom")
        self.head.position = [0, 12*ps, -6*ps] # Forward a bit
        
        # BODY
        # 16 long (z), 10 wide (x), 8 high (y)
        # Texture mapping might be tricky with standard box, using generic mapping for now
        self.body = ModelPart(64, 32, 28, 8, 10, 16, 8) 
        # width, depth(length), height
        # Rotate body 90 degrees X usually?
        # Let's just build it as a box 10x8x16 (WxHxL)
        self.body._build_mesh_custom(28, 8, 10, 8, 16, ps, pivot="center")
        self.body.position = [0, 8*ps, 0] # Center
        # Rotate body mesh to be horizontal? 
        # _build_mesh_custom creates a box WxHxD.
        
        # LEGS (4)
        leg_h = 6
        leg_w = 4
        leg_d = 4
        
        # Front Left
        self.fl_leg = ModelPart(64, 32, 0, 16, 4, 6, 4)
        self.fl_leg._build_mesh_custom(0, 16, 4, 6, 4, ps, pivot="top")
        self.fl_leg.position = [-3*ps, 6*ps, -7*ps]

        # Front Right
        self.fr_leg = ModelPart(64, 32, 0, 16, 4, 6, 4)
        self.fr_leg._build_mesh_custom(0, 16, 4, 6, 4, ps, pivot="top")
        self.fr_leg.position = [3*ps, 6*ps, -7*ps]
        
        # Back Left
        self.bl_leg = ModelPart(64, 32, 0, 16, 4, 6, 4)
        self.bl_leg._build_mesh_custom(0, 16, 4, 6, 4, ps, pivot="top")
        self.bl_leg.position = [-3*ps, 6*ps, 7*ps]

        # Back Right
        self.br_leg = ModelPart(64, 32, 0, 16, 4, 6, 4)
        self.br_leg._build_mesh_custom(0, 16, 4, 6, 4, ps, pivot="top")
        self.br_leg.position = [3*ps, 6*ps, 7*ps]
        
        self.parts = [self.head, self.body, self.fl_leg, self.fr_leg, self.bl_leg, self.br_leg]
        
        # Mapping helpers for animation
        self.legs = [self.fl_leg, self.fr_leg, self.bl_leg, self.br_leg]

    def update(self, delta_time):
        super().update(delta_time)
        
        # Pig Specific Animation Overrides
        if self.animation_state == 'walk':
            # 4 Leg Animation
            angle = math.sin(self.anim_time) * 0.6
            self.fl_leg.rotation[0] = angle
            self.fr_leg.rotation[0] = -angle
            self.bl_leg.rotation[0] = -angle
            self.br_leg.rotation[0] = angle
        else:
            for leg in self.legs:
                leg.rotation[0] *= 0.8

    def is_position_safe(self, x, y, z):
        bx, by, bz = int(math.floor(x)), int(math.floor(y)), int(math.floor(z))
        blk_body = self.world.get_block_number((bx, by, bz))
        blk_feet = self.world.get_block_number((bx, by, bz))
        if blk_body in [8, 9] or blk_feet in [8, 9]: return False
        floor_y = int(math.floor(y))
        safe_drop = False
        for dy in range(1, 5): 
            blk = self.world.get_block_number((bx, floor_y - dy, bz))
            if blk != 0 and blk not in [8, 9]: 
                safe_drop = True
                break
        if not safe_drop: return False 
        return True

    def draw(self, p, v):
        if not self.shader: return
        self.shader.use()
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.id)
        gl.glUniform1i(self.tex_loc, 0)
        
        # Visual Effect if hurt
        hurt_val = 0.0
        if self.hurt_timer > 0:
            hurt_val = 0.7 # 70% red mix
        
        gl.glUniform1f(self.hurt_loc, hurt_val)
        
        m = matrix.Matrix()
        m.load_identity()
        m.translate(self.position[0], self.position[1], self.position[2])
        m.rotate_2d(-self.rotation[0] - math.pi, 0)
        pv = p * v * m
        for part in self.parts:
            part.draw(pv, self.matrix_loc)
        
        self.shader.stop()

# Helper
def _custom_build(self, ux, uy, sx, sy, sz, ps, pivot="top"):
    w, h, d = sx*ps, sy*ps, sz*ps
    if pivot == "top": y_top, y_bot = 0, -h
    else: y_top, y_bot = h, 0
    x_left, x_right = -w/2, w/2
    z_front, z_back = d/2, -d/2
    x1, y1, z1 = x_left, y_bot, z_back
    x2, y2, z2 = x_right, y_top, z_front
    def uv(u_pix, v_pix): return (u_pix / 64.0, 1.0 - (v_pix / 64.0))
    def quad(bl, br, tr, tl, u_min, v_min, u_w, u_h, shade, flip_u=False):
        coords = [bl, br, tr, tl]
        u1 = u_min if not flip_u else u_min + u_w
        u2 = u_min + u_w if not flip_u else u_min
        t_bl = uv(u1, v_min + u_h)
        t_br = uv(u2, v_min + u_h)
        t_tr = uv(u2, v_min)
        t_tl = uv(u1, v_min)
        uvs = [t_bl, t_br, t_tr, t_tl]
        res = []
        indices = [0, 1, 2, 0, 2, 3]
        for idx in indices:
            res.extend(coords[idx]); res.extend(uvs[idx]); res.append(shade)
        return res
    verts = []
    verts.extend(quad((x1,y1,z2), (x2,y1,z2), (x2,y2,z2), (x1,y2,z2), ux+sz, uy+sz, sx, sy, 0.8))
    verts.extend(quad((x2,y1,z1), (x1,y1,z1), (x1,y2,z1), (x2,y2,z1), ux+sz+sx+sz, uy+sz, sx, sy, 0.8))
    verts.extend(quad((x2,y1,z2), (x2,y1,z1), (x2,y2,z1), (x2,y2,z2), ux, uy+sz, sz, sy, 0.6, flip_u=True))
    verts.extend(quad((x1,y1,z1), (x1,y1,z2), (x1,y2,z2), (x1,y2,z1), ux+sz+sx, uy+sz, sz, sy, 0.6, flip_u=True))
    verts.extend(quad((x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1), ux+sz, uy, sx, sz, 1.0))
    verts.extend(quad((x1,y1,z1), (x2,y1,z1), (x2,y1,z2), (x1,y1,z2), ux+sz+sx, uy, sx, sz, 0.5))
    self.vertex_count = len(verts) // 6
    self.vao = gl.GLuint(0)
    gl.glGenVertexArrays(1, self.vao)
    gl.glBindVertexArray(self.vao)
    self.vbo = gl.GLuint(0)
    gl.glGenBuffers(1, self.vbo)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
    c_verts = (gl.GLfloat * len(verts))(*verts)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, len(verts) * 4, c_verts, gl.GL_STATIC_DRAW)
    stride = 6 * 4
    gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, 0)
    gl.glEnableVertexAttribArray(0)
    gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, 12)
    gl.glEnableVertexAttribArray(1)
    gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, 20)
    gl.glEnableVertexAttribArray(2)
    gl.glBindVertexArray(0)
ModelPart._build_mesh_custom = _custom_build
