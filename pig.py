import math
import random
import pyglet
from pyglet import gl
import ctypes
import mob
import matrix

class Pig(mob.Mob):
    def __init__(self, world, position=(0, 0, 0)):
        # Initialize Entity/Mob basics manually to avoid calling _build_steve from Mob.__init__
        # Logic copied from Mob.__init__ but calling _build_pig
        super(mob.Mob, self).__init__(world) # Call Entity.__init__
        
        self.width = 0.9
        self.height = 0.9
        self.position = list(position)
        self.gravity_enabled = True # Re-enabled gravity for AI
        self.ai_timer = 0.0
        self.ai_state = 'idle'
        self.target_yaw = 0.0 
        self.dest_yaw = 0.0   
        
        self.texture = None
        self.shader = None
        self._init_gl()
        self.parts = []
        
        self._build_pig()
        
        self.test_anim_phase = 0
        self.test_anim_timer = 0.0
        self.initial_head_rot = [0, math.pi, 0] # Default forward

        self.animation_state = None
        self.anim_time = 0.0
        
        # Sound timers
        self.idle_sound_timer = random.uniform(5.0, 15.0)
        self.step_sound_timer = 0.0
        self.sound_manager = getattr(world, 'sound_manager', None) # Fallback to world attribute if injected

    def _init_gl(self):
        try:
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
            uniform float hurt_intensity; 

            void main()
            {
                vec4 tex_color = texture(texture_sampler, v_tex_coords);
                if(tex_color.a < 0.1) discard;
                
                vec3 mixed_color = mix(tex_color.rgb * v_shading, vec3(1.0, 0.0, 0.0), hurt_intensity);
                out_color = vec4(mixed_color, tex_color.a);
            }
            """
            
            self.shader = pyglet.graphics.shader.ShaderProgram(
                pyglet.graphics.shader.Shader(vertex_source, 'vertex'),
                pyglet.graphics.shader.Shader(fragment_source, 'fragment')
            )
            self.matrix_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'matrix'))
            self.tex_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'texture_sampler'))
            self.hurt_loc = gl.glGetUniformLocation(self.shader.id, ctypes.create_string_buffer(b'hurt_intensity'))
            
            # Load Pig Texture
            try:
                img = pyglet.image.load("textures/pig.png")
            except:
                img = pyglet.image.load("models/pig.png")
                
            self.texture = img.get_texture()
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        except Exception as e:
            print(f"Pig Init Error: {e}")

    def _build_pig(self):
        ps = 0.06
        
        # Helper for standard box build with 64x32 texture assumption
        def build_part_mesh(part, ux, uy, sx, sy, sz, ps, pivot="top"):
            w, h, d = sx*ps, sy*ps, sz*ps
            if pivot == "top": y_top, y_bot = 0, -h
            elif pivot == "bottom": y_top, y_bot = h, 0
            else: y_top, y_bot = h/2, -h/2 # center
            
            x_left, x_right = -w/2, w/2
            z_front, z_back = d/2, -d/2
            x1, y1, z1 = x_left, y_bot, z_back 
            x2, y2, z2 = x_right, y_top, z_front
            
            # Pig texture is 64x32
            def uv(u_pix, v_pix): return (u_pix / 64.0, 1.0 - (v_pix / 32.0))
            
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
            # Standard Box Mapping
            # Front (Z+)
            verts.extend(quad((x1,y1,z2), (x2,y1,z2), (x2,y2,z2), (x1,y2,z2), ux+sz, uy+sz, sx, sy, 0.8))
            # Back (Z-)
            verts.extend(quad((x2,y1,z1), (x1,y1,z1), (x1,y2,z1), (x2,y2,z1), ux+sz+sx+sz, uy+sz, sx, sy, 0.8))
            # Right (X+)
            verts.extend(quad((x2,y1,z2), (x2,y1,z1), (x2,y2,z1), (x2,y2,z2), ux, uy+sz, sz, sy, 0.6, flip_u=True))
            # Left (X-)
            verts.extend(quad((x1,y1,z1), (x1,y1,z2), (x1,y2,z2), (x1,y2,z1), ux+sz+sx, uy+sz, sz, sy, 0.6, flip_u=True))
            # Top (Y+)
            verts.extend(quad((x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1), ux+sz, uy, sx, sz, 1.0))
            # Bot (Y-)
            verts.extend(quad((x1,y1,z1), (x2,y1,z1), (x2,y1,z2), (x1,y1,z2), ux+sz+sx, uy, sx, sz, 0.5))
            
            part.vertex_count = len(verts) // 6
            part.vao = gl.GLuint(0)
            gl.glGenVertexArrays(1, part.vao)
            gl.glBindVertexArray(part.vao)
            part.vbo = gl.GLuint(0)
            gl.glGenBuffers(1, part.vbo)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, part.vbo)
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

        # 1. HEAD (Custom build with Snout)
        self.head = mob.ModelPart(64, 32, 0, 0, 8, 8, 8)
        
        def build_head_with_snout(part, ps):
            # Main Head (8x8x8)
            # Use logic similar to helper but inline to add snout
            ux, uy, sx, sy, sz = 0, 0, 8, 8, 8
            w, h, d = sx*ps, sy*ps, sz*ps
            y_bot, y_top = 0, h
            x_left, x_right = -w/2, w/2
            z_front, z_back = d/2, -d/2 
            x1, y1, z1 = x_left, y_bot, z_back
            x2, y2, z2 = x_right, y_top, z_front
            
            verts = []
            def uv(u, v): return (u / 64.0, 1.0 - (v / 32.0))
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
                # Ensure CCW winding: BL, BR, TR, TL -> 0,1,2, 0,2,3
                indices = [0, 1, 2, 0, 2, 3]
                for idx in indices:
                    res.extend(coords[idx]); res.extend(uvs[idx]); res.append(shade)
                return res

            # Head Faces
            verts.extend(quad((x1,y1,z2), (x2,y1,z2), (x2,y2,z2), (x1,y2,z2), ux+sz, uy+sz, sx, sy, 0.8)) # Front
            verts.extend(quad((x2,y1,z1), (x1,y1,z1), (x1,y2,z1), (x2,y2,z1), ux+sz+sx+sz, uy+sz, sx, sy, 0.8)) # Back
            verts.extend(quad((x2,y1,z2), (x2,y1,z1), (x2,y2,z1), (x2,y2,z2), ux, uy+sz, sz, sy, 0.6, flip_u=True)) # Right
            verts.extend(quad((x1,y1,z1), (x1,y1,z2), (x1,y2,z2), (x1,y2,z1), ux+sz+sx, uy+sz, sz, sy, 0.6, flip_u=True)) # Left
            verts.extend(quad((x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1), ux+sz, uy, sx, sz, 1.0)) # Top
            verts.extend(quad((x1,y1,z1), (x2,y1,z1), (x2,y1,z2), (x1,y1,z2), ux+sz+sx, uy, sx, sz, 0.5)) # Bot
            
            # Snout (4x3x1)
            sw, sh, sd = 4*ps, 3*ps, 1*ps
            sx_s, sy_s, sz_s = 4, 3, 1
            ux_s, uy_s = 16, 16
            
            y_s_bot = 1 * ps
            y_s_top = y_s_bot + sh
            x_s_left = -sw/2
            x_s_right = sw/2
            z_s_back = z2 # On Face
            z_s_front = z2 + sd
            
            xs1, ys1, zs1 = x_s_left, y_s_bot, z_s_back
            xs2, ys2, zs2 = x_s_right, y_s_top, z_s_front
            
            verts.extend(quad((xs1,ys1,zs2), (xs2,ys1,zs2), (xs2,ys2,zs2), (xs1,ys2,zs2), ux_s+sz_s, uy_s+sz_s, sx_s, sy_s, 0.8)) # Front
            verts.extend(quad((xs1,ys2,zs2), (xs2,ys2,zs2), (xs2,ys2,zs1), (xs1,ys2,zs1), ux_s+sz_s, uy_s, sx_s, sz_s, 1.0)) # Top
            verts.extend(quad((xs1,ys1,zs1), (xs2,ys1,zs1), (xs2,ys1,zs2), (xs1,ys1,zs2), ux_s+sz_s+sx_s, uy_s, sx_s, sz_s, 0.5)) # Bot
            verts.extend(quad((xs2,ys1,zs2), (xs2,ys1,zs1), (xs2,ys2,zs1), (xs2,ys2,zs2), ux_s, uy_s+sz_s, sz_s, sy_s, 0.6, flip_u=False)) # Right
            verts.extend(quad((xs1,ys1,zs1), (xs1,ys1,zs2), (xs1,ys2,zs2), (xs1,ys2,zs1), ux_s+sz_s+sx_s, uy_s+sz_s, sz_s, sy_s, 0.6, flip_u=False)) # Left
            
            part.vertex_count = len(verts) // 6
            part.vao = gl.GLuint(0)
            gl.glGenVertexArrays(1, part.vao)
            gl.glBindVertexArray(part.vao)
            part.vbo = gl.GLuint(0)
            gl.glGenBuffers(1, part.vbo)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, part.vbo)
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

        build_head_with_snout(self.head, ps)
        self.head.position = [0, 9*ps, -12*ps] # Forward
        self.head.rotation = [0, math.pi, 0] # Rotate 180 to face Correctly

        # 2. BODY (Standard Build + Rotation)
        # Texture: 28, 8. Size: 10, 16, 8.
        self.body = mob.ModelPart(64, 32, 28, 8, 10, 16, 8)
        build_part_mesh(self.body, 28, 8, 10, 16, 8, ps, pivot="center")
        
        # Rotate Body 90 degrees around X to lay flat (flipped to match texture top/bottom)
        self.body.rotation = [math.pi/2, 0, 0] 
        self.body.position = [0, 10*ps, 0]

        # 3. LEGS
        leg_y = 6*ps 
        leg_h = 6
        
        self.leg1 = mob.ModelPart(64, 32, 0, 16, 4, leg_h, 4)
        build_part_mesh(self.leg1, 0, 16, 4, leg_h, 4, ps, pivot="top")
        self.leg1.position = [-3*ps, leg_y, 6*ps]

        self.leg2 = mob.ModelPart(64, 32, 0, 16, 4, leg_h, 4)
        build_part_mesh(self.leg2, 0, 16, 4, leg_h, 4, ps, pivot="top")
        self.leg2.position = [3*ps, leg_y, 6*ps]

        self.leg3 = mob.ModelPart(64, 32, 0, 16, 4, leg_h, 4)
        build_part_mesh(self.leg3, 0, 16, 4, leg_h, 4, ps, pivot="top")
        self.leg3.position = [-3*ps, leg_y, -6*ps]

        self.leg4 = mob.ModelPart(64, 32, 0, 16, 4, leg_h, 4)
        build_part_mesh(self.leg4, 0, 16, 4, leg_h, 4, ps, pivot="top")
        self.leg4.position = [3*ps, leg_y, -6*ps]

        self.parts = [self.head, self.body, self.leg1, self.leg2, self.leg3, self.leg4]

    def draw(self, p, v):
        # Override to disable face culling
        if not self.shader: return
        self.shader.use()
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.id)
        gl.glUniform1i(self.tex_loc, 0)
        
        hurt_val = 0.0
        if self.hurt_timer > 0:
            hurt_val = 0.7 
        
        gl.glUniform1f(self.hurt_loc, hurt_val)
        
        m = matrix.Matrix()
        m.load_identity()
        m.translate(self.position[0], self.position[1], self.position[2])
        m.rotate_2d(-self.rotation[0] - math.pi, 0)
        pv = p * v * m
        
        gl.glDisable(gl.GL_CULL_FACE) # Disable culling for Pig to ensure all manual quads show
        for part in self.parts:
            part.draw(pv, self.matrix_loc)
        gl.glEnable(gl.GL_CULL_FACE)
        
        self.shader.stop()

    def on_hit(self, attacker):
        """Called when mob acts on damage. Triggers flee behavior."""
        print("Pig Hit! Fleeing!")
        self.ai_state = 'flee'
        self.ai_timer = 5.0 # Run for 5 seconds
        self.attacker = attacker
        
        # Immediate turn away
        if attacker:
            dx = self.position[0] - attacker.position[0]
            dz = self.position[2] - attacker.position[2]
            self.target_yaw = -math.atan2(dx, dz)

    def trigger_test_animation(self):
        self.test_anim_phase = 1
        self.test_anim_timer = 0.0
        self.initial_head_rot = list(self.head.rotation)

    def update(self, delta_time):
        # Handle Test Animation overrides
        if self.test_anim_phase > 0:
            self.test_anim_timer += delta_time
            t = self.test_anim_timer
            
            # Phase 1: Head Shake (Left/Right)
            if self.test_anim_phase == 1:
                angle = math.sin(t * 10) * 0.5
                self.head.rotation = [self.initial_head_rot[0], self.initial_head_rot[1] + angle, self.initial_head_rot[2]]
                if t > 2.0:
                    self.test_anim_phase = 2
                    self.test_anim_timer = 0.0
                    self.head.rotation = list(self.initial_head_rot)

            # Phase 2: Head Nod (Up/Down)
            elif self.test_anim_phase == 2:
                angle = math.sin(t * 10) * 0.5
                self.head.rotation = [angle, self.initial_head_rot[1], self.initial_head_rot[2]]
                if t > 2.0:
                    self.test_anim_phase = 3
                    self.test_anim_timer = 0.0
                    self.head.rotation = list(self.initial_head_rot)

            # Phase 3: Walk Animation (Legs)
            elif self.test_anim_phase == 3:
                speed = 10
                leg_move = math.sin(t * speed) * 0.5
                self.leg1.rotation = [leg_move, 0, 0]
                self.leg4.rotation = [leg_move, 0, 0]
                self.leg2.rotation = [-leg_move, 0, 0]
                self.leg3.rotation = [-leg_move, 0, 0]
                
                if t > 2.0:
                    self.test_anim_phase = 0
                    self.test_anim_timer = 0.0
                    self.leg1.rotation = [0,0,0]
                    self.leg2.rotation = [0,0,0]
                    self.leg3.rotation = [0,0,0]
                    self.leg4.rotation = [0,0,0]

            super(mob.Mob, self).update(delta_time)
            return

        # --- AI LOGIC (Resumed) ---
        
        self.ai_timer -= delta_time
        
        # --- State Machine Trigger ---
        if self.ai_state == 'flee':
            print(f"Fleeing: TargetYaw={self.target_yaw} Pos={self.position}")
            if self.ai_timer <= 0:
                self.ai_state = 'idle' # Stop fleeing
                self.attacker = None
        elif self.ai_timer <= 0:
            self.ai_timer = random.uniform(2.0, 5.0)
            if random.random() < 0.7:
                self.ai_state = 'pre_walk_look'
                self.dest_yaw = random.choice([0, math.pi/2, math.pi, -math.pi/2])
                # Keep target_yaw same as current to freeze body
                self.target_yaw = self.target_yaw 
            else:
                self.ai_state = 'idle'
        
        # --- State Handlers ---
        
        # Flee Logic
        if self.ai_state == 'flee':
            # Run away from attacker position!
            # Continuously update direction if attacker is known
            if hasattr(self, 'attacker') and self.attacker:
                # Vector FROM attacker TO self
                dx = self.position[0] - self.attacker.position[0]
                dz = self.position[2] - self.attacker.position[2]
                
                # Check 3 directions: Straight Away, Left-Skew, Right-Skew
                # To find safest
                base_angle = -math.atan2(dx, dz)
                
                best_yaw = base_angle
                best_safety = -1
                
                # Check directions
                for offset in [0, -math.pi/4, math.pi/4]:
                    check_yaw = base_angle + offset
                    # Project forward
                    check_dist = 2.0 
                    cx = self.position[0] + math.sin(-check_yaw) * check_dist
                    cz = self.position[2] + math.cos(-check_yaw) * check_dist
                    cy = self.position[1]
                    
                    if self.is_position_safe(cx, cy, cz):
                         # If safe, this is a candidate. 
                         # Preference to offset 0 (Straight away)
                         score = 10 if offset == 0 else 5
                         if score > best_safety:
                             best_safety = score
                             best_yaw = check_yaw
                
                # If everything implies doom, just run straight away in panic (or keep current)
                # Apply Smooth Turn to Best Yaw
                self.target_yaw = best_yaw
            
            # Allow smooth rotation to handle it
            
            # Head looks forward! (Panic)
            # Pig head intrinsic offset of Pi.
            target_h_rel = (self.target_yaw - self.rotation[0] + math.pi) % (math.pi*2) - math.pi + math.pi
            self.head.rotation[1] = target_h_rel

        # 1. Look at target (Head only)
        elif self.ai_state == 'pre_walk_look':
            current_body = self.rotation[0]
            # Head World = Dest Yaw. Head Rel = Dest - Body + Pi.
            wanted_head_rel = (self.dest_yaw - current_body + math.pi) % (math.pi * 2) - math.pi
            wanted_head_rel += math.pi 
            
            # Smooth rotate head
            curr_h = self.head.rotation[1]
            diff = (wanted_head_rel - curr_h + math.pi) % (math.pi*2) - math.pi
            
            h_speed = 8.0 * delta_time
            if abs(diff) < h_speed:
                self.head.rotation[1] = wanted_head_rel
                self.ai_state = 'pre_walk_turn'
                self.target_yaw = self.dest_yaw 
            else:
                self.head.rotation[1] += math.copysign(h_speed, diff)

        # 2. Turn Body (Head stays locked on target)
        elif self.ai_state == 'pre_walk_turn':
            # Counter-rotate head to keep looking at target while body turns
            target_h_rel = (self.dest_yaw - self.rotation[0] + math.pi) % (math.pi*2) - math.pi + math.pi
            
            curr_h = self.head.rotation[1]
            diff = (target_h_rel - curr_h + math.pi) % (math.pi*2) - math.pi
            
            h_speed = 6.0 * delta_time
            if abs(diff) < h_speed:
                self.head.rotation[1] = target_h_rel
            else:
                self.head.rotation[1] += math.copysign(h_speed, diff)

            # Check if Body is aligned (Body rotation handled below generic block)
            curr_b = self.rotation[0]
            dist = abs((self.target_yaw - curr_b + math.pi) % (math.pi*2) - math.pi)
            if dist < 0.05:
                self.ai_state = 'walk'

        elif self.ai_state == 'idle':
            target_h = math.pi # Default forward (relative)
            
            # Look at player if close
            looking_at_player = False
            if hasattr(self, 'player') and self.player:
                dx = self.position[0] - self.player.position[0]
                dy = self.position[1] - self.player.position[1] # Use body Y or head Y?
                dz = self.position[2] - self.player.position[2]
                dist_sq = dx*dx + dy*dy + dz*dz
                
                if dist_sq < 36.0: # 6 blocks
                    # Face Player
                    # Vector Used: (dx, dz) which is Self - Player.
                    # We want to look AT Player.
                    # Vector Self->Player is (-dx, -dz).
                    # Yaw = -atan2(x, z).
                    # atan2(-dx, -dz) -> Angle of vector to player.
                    # My previous code was -atan2(-dx, -dz).
                    # If that looked backwards, maybe the - before atan2 was wrong OOR the 0-ref is different.
                    # Let's try adding Pi to flip it 180 degrees.
                    target_yaw = -math.atan2(-dx, -dz) + math.pi
                    
                    # Target relative head yaw
                    # Head World = Body + Rel - Pi
                    # Rel = Head World - Body + Pi
                    target_h_rel = (target_yaw - self.rotation[0] + math.pi) % (math.pi*2) - math.pi + math.pi
                    
                    # Rel IS (target - body) + Pi.
                    # We want to clamp deviations from Pi (Forward relative to body).
                    # Deviation = Rel - Pi.
                    dev = (target_h_rel - math.pi + math.pi) % (math.pi*2) - math.pi
                    
                    # Clamp Deviation
                    max_angle = math.pi / 3.0 # 60 degrees
                    if dev > max_angle: dev = max_angle
                    if dev < -max_angle: dev = -max_angle
                    
                    desired_rel = math.pi + dev
                    
                    # Smooth Rotation
                    curr = self.head.rotation[1]
                    diff = (desired_rel - curr + math.pi) % (math.pi*2) - math.pi
                    self.head.rotation[1] += diff * delta_time * 5.0
                    looking_at_player = True

            if not looking_at_player:
                target_h = math.sin(pyglet.clock.get_default().time() * 0.5) * 0.5
                
                # Smooth return to idle anim
                desired = math.pi + target_h
                curr = self.head.rotation[1]
                diff = (desired - curr + math.pi) % (math.pi*2) - math.pi
                self.head.rotation[1] += diff * delta_time * 2.0

        # Body Smooth Rotation
        current_yaw = self.rotation[0]
        diff = (self.target_yaw - current_yaw + math.pi) % (math.pi * 2) - math.pi
        
        # Turn faster if fleeing
        turn_mult = 3.0 if self.ai_state == 'flee' else 1.0
        rot_speed = 4.0 * delta_time * turn_mult
        if abs(diff) < rot_speed:
            self.rotation[0] = self.target_yaw
        else:
            self.rotation[0] += math.copysign(rot_speed, diff)

        # 3. Walk Physics
        if self.ai_state == 'walk' or self.ai_state == 'flee':
            # SPRINT if fleeing
            speed = 3.0 if self.ai_state == 'flee' else 1.0 
            
            # Angle: self.rotation[0]
            dx = math.sin(-self.rotation[0]) * speed
            dz = math.cos(-self.rotation[0]) * speed
            
            # Safety Check
            check_dist = 0.6
            cx = self.position[0] + math.sin(-self.rotation[0]) * check_dist
            cz = self.position[2] + math.cos(-self.rotation[0]) * check_dist
            cy = self.position[1]
            
            if self.is_position_safe(cx, cy, cz) or self.ai_state == 'flee': 
                # Fleeing might override simple safety check? 
                # No, we don't want to fall off cliffs even if panic.
                # But our "is_position_safe" is simplistic (1 block lookahead).
                # If logic above picked "best_yaw", we trust it.
                # Just obey safety for normal walk. For flee, rely on selected yaw being safe.
                # But physics update needs to apply accel.
                
                # Double check: if we are fleeing and blocked by wall, jump?
                if self.ai_state == 'flee':
                     self.accel[0] = dx
                     self.accel[2] = dz
                     # Jump if stuck?
                     horz_vel = math.sqrt(self.velocity[0]**2 + self.velocity[2]**2)
                     if self.grounded and horz_vel < 0.2: # Stuck
                         self.jump()
                elif self.is_position_safe(cx, cy, cz):
                    self.accel[0] = dx
                    self.accel[2] = dz
                else: 
                     # Stop if unsafe path in walk mode
                     self.velocity = [0, self.velocity[1], 0]
                     self.ai_state = 'idle'
            else:
                self.velocity = [0, self.velocity[1], 0]
                self.ai_state = 'idle'
            
            horz_speed = math.sqrt(self.velocity[0]**2 + self.velocity[2]**2)
            if self.grounded and horz_speed < 0.1 and self.ai_state == 'flee': # Jump if slow fleeing
                 # Only if hitting wall
                 pass
            elif self.grounded and horz_speed < 0.1: # Stuck routine
                 self.jump()
        
        super(mob.Mob, self).update(delta_time)
        if self.hurt_timer > 0:
            self.hurt_timer -= delta_time

        # Animation Logic (Walking)
        speed_horz = math.sqrt(self.velocity[0]**2 + self.velocity[2]**2)
        if speed_horz > 0.1 and (self.ai_state == 'walk' or self.ai_state == 'flee'):
            # Speed up animation if fled
            anim_speed = 20 if self.ai_state == 'flee' else 10
            
            self.anim_time += delta_time * anim_speed
            angle = math.sin(self.anim_time) * 0.6
            # Quadruped Gait
            self.leg1.rotation[0] = angle
            self.leg4.rotation[0] = angle
            self.leg2.rotation[0] = -angle
            self.leg3.rotation[0] = -angle
        else:
            # Return to stand
            self.leg1.rotation[0] *= 0.8
            self.leg2.rotation[0] *= 0.8
            self.leg3.rotation[0] *= 0.8
            self.leg4.rotation[0] *= 0.8
            self.step_sound_timer = 0.0

        # Sound Effects Logic
        if self.sound_manager:
            # Idle sound
            self.idle_sound_timer -= delta_time
            if self.idle_sound_timer <= 0:
                self.sound_manager.play("pig_say", position=self.position)
                self.idle_sound_timer = random.uniform(5.0, 15.0)
            
            # Step sound
            if speed_horz > 0.1 and self.grounded:
                # Interval based on speed
                interval = 0.35 if self.ai_state == 'flee' else 0.5
                self.step_sound_timer += delta_time
                if self.step_sound_timer >= interval:
                    self.sound_manager.play("pig_step", position=self.position)
                    self.step_sound_timer = 0
            else:
                self.step_sound_timer = 0

    def take_damage(self, amount):
        if self.dead or self.hurt_timer > 0:
            return
            
        super(mob.Mob, self).take_damage(amount)
        
        if self.sound_manager:
            if self.dead:
                self.sound_manager.play("pig_death", position=self.position)
            else:
                self.sound_manager.play("pig_say", position=self.position) # Use say for hurt as well
                
    def is_position_safe(self, x, y, z):
        bx, by, bz = int(math.floor(x)), int(math.floor(y)), int(math.floor(z))
        blk_body = self.world.get_block_number((bx, by, bz))
        if blk_body in [8, 9]: return False # Water/Lava unsafe?
        floor_y = int(math.floor(y))
        safe_drop = False
        for dy in range(1, 4): # Check drop depth
            blk = self.world.get_block_number((bx, floor_y - dy, bz))
            if blk != 0 and blk not in [8, 9]: 
                safe_drop = True
                break
        if not safe_drop: return False 
        return True
