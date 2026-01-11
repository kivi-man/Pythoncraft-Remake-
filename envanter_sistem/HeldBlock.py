# HeldBlock.py (Optimize Edilmiş)
from ursina import *
from ursina.shaders import unlit_shader
import math

class HeldBlock(Entity):
    """
    Oyuncunun elinde tuttuğu blok (Minecraft tarzı)
    
    OPTİMİZASYON:
    - Update fonksiyonu sadece gerektiğinde çalışır
    - Gereksiz hesaplamalar kaldırıldı
    - Animasyonlar event-bazlı (sürekli hesaplama yok)
    """
    def __init__(self, block_cells, atlas_texture, atlas_cols_total, atlas_rows, **kwargs):
        super().__init__(parent=camera, **kwargs)
        
        self.block_cells = block_cells
        self.atlas_texture = atlas_texture
        self.atlas_cols_total = atlas_cols_total
        self.atlas_rows = atlas_rows
        self.current_block = None
        self.block_entity = None
        
        # Pozisyon ayarları
        self.default_position = Vec3(0.4, -0.3, 0.5)
        self.position = self.default_position
        self.default_rotation = Vec3(0, 45, 0)
        self.rotation = self.default_rotation
        self.scale = 0.3
        
        # Animasyon değişkenleri
        self.bob_time = 0
        self.bob_speed = 8
        self.bob_amount = 0.015
        self.sway_amount = 0.02
        
        # Aksiyon animasyonları
        self.is_placing = False
        self.is_breaking = False
        self.action_time = 0
        self.action_duration = 0.2
        
        # Önceki kamera rotasyonu
        self.prev_camera_rotation = Vec3(camera.rotation)
        
        # OPTİMİZASYON: Hareket durumu kontrolü
        self.was_moving = False
    
    def create_block_mesh(self, block_type):
        """Blok için mesh oluştur"""
        if block_type not in self.block_cells:
            return None
        
        vertices = []
        triangles = []
        uvs = []
        
        # Küp yüzleri
        faces_data = [
            [(0,0,0), (1,0,0), (1,1,0), (0,1,0)],
            [(1,0,1), (0,0,1), (0,1,1), (1,1,1)],
            [(0,0,1), (0,0,0), (0,1,0), (0,1,1)],
            [(1,0,0), (1,0,1), (1,1,1), (1,1,0)],
            [(0,0,1), (1,0,1), (1,0,0), (0,0,0)],
            [(0,1,0), (1,1,0), (1,1,1), (0,1,1)]
        ]
        
        face_names = ['front', 'back', 'left', 'right', 'bottom', 'top']
        idx = 0
        
        for face_idx, face_verts in enumerate(faces_data):
            for v in face_verts:
                vertices.append(Vec3(v[0]-0.5, v[1]-0.5, v[2]-0.5))
            
            triangles.extend([idx, idx+1, idx+2, idx, idx+2, idx+3])
            
            ax, ay = self.block_cells[block_type][face_names[face_idx]]
            uv_coords = [
                (ax/self.atlas_cols_total, ay/self.atlas_rows),
                ((ax+1)/self.atlas_cols_total, ay/self.atlas_rows),
                ((ax+1)/self.atlas_cols_total, (ay+1)/self.atlas_rows),
                (ax/self.atlas_cols_total, (ay+1)/self.atlas_rows)
            ]
            uvs.extend(uv_coords)
            
            idx += 4
        
        mesh = Mesh(vertices=vertices, triangles=triangles, uvs=uvs, mode='triangle')
        mesh.generate()
        return mesh
    
    def set_block(self, block_type):
        """Eldeki bloğu değiştir"""
        if block_type == self.current_block:
            return
        
        if self.block_entity:
            destroy(self.block_entity)
            self.block_entity = None
        
        self.current_block = block_type
        
        if block_type and block_type in self.block_cells:
            mesh = self.create_block_mesh(block_type)
            if mesh:
                self.block_entity = Entity(
                    parent=self,
                    model=mesh,
                    texture=self.atlas_texture,
                    shader=unlit_shader,
                    scale=1
                )
    
    def play_place_animation(self):
        """Blok yerleştirme animasyonu"""
        self.is_placing = True
        self.action_time = 0
    
    def play_break_animation(self):
        """Blok kırma animasyonu"""
        self.is_breaking = True
        self.action_time = 0
    
    def update_walking_animation(self, dt):
        """Yürürken sallanma animasyonu (OPTİMİZE - Sadece hareket varsa çalışır)"""
        is_moving = any([held_keys['w'], held_keys['a'], held_keys['s'], held_keys['d']])
        
        if is_moving:
            self.bob_time += dt * self.bob_speed
            
            bob_offset = math.sin(self.bob_time) * self.bob_amount
            sway_offset = math.sin(self.bob_time * 0.5) * self.sway_amount
            
            self.position = self.default_position + Vec3(sway_offset, bob_offset, 0)
            self.was_moving = True
        else:
            # Duruyorsa yavaşça varsayılan konuma dön (Sadece hareket bittiyse)
            if self.was_moving:
                self.bob_time = 0
                self.position = lerp(self.position, self.default_position, dt * 10)
                
                # Pozisyon yeterince yaklaştıysa artık update yapma
                if distance(self.position, self.default_position) < 0.001:
                    self.position = self.default_position
                    self.was_moving = False
    
    def update_camera_sway(self):
        """Kamera hareketiyle sallanma (OPTİMİZE - Sadece kamera hareket ettiyse)"""
        rotation_delta = camera.rotation - self.prev_camera_rotation
        
        # Eğer kamera hareket etmediyse hesaplama yapma
        if abs(rotation_delta.x) < 0.01 and abs(rotation_delta.y) < 0.01:
            return
        
        sway_x = -rotation_delta.y * 0.01
        sway_y = -rotation_delta.x * 0.01
        
        target_rotation = self.default_rotation + Vec3(
            clamp(sway_y, -5, 5),
            clamp(sway_x, -5, 5),
            0
        )
        
        self.rotation = lerp(self.rotation, target_rotation, time.dt * 10)
        self.prev_camera_rotation = Vec3(camera.rotation)
    
    def update_action_animations(self, dt):
        """Aksiyon animasyonlarını güncelle"""
        if self.is_placing:
            self.action_time += dt
            progress = min(self.action_time / self.action_duration, 1.0)
            
            offset = math.sin(progress * math.pi) * 0.15
            self.position = self.default_position + Vec3(0, 0, offset)
            
            if progress >= 1.0:
                self.is_placing = False
                self.position = self.default_position
        
        elif self.is_breaking:
            self.action_time += dt
            progress = min(self.action_time / self.action_duration, 1.0)
            
            swing = math.sin(progress * math.pi) * 15
            self.rotation = self.default_rotation + Vec3(0, 0, swing)
            
            if progress >= 1.0:
                self.is_breaking = False
                self.rotation = self.default_rotation
    
    def update(self):
        """
        Her frame güncelle
        
        OPTİMİZASYON: Sadece gerekli durumlarda hesaplama yapar
        """
        if not self.block_entity:
            return
        
        dt = time.dt
        
        # Animasyonları güncelle (Sadece aktif olduklarında)
        if self.is_placing or self.is_breaking:
            self.update_action_animations(dt)
        else:
            # Normal animasyonlar (Sadece hareket varsa)
            self.update_walking_animation(dt)
            self.update_camera_sway()
    
    def hide(self):
        """Bloğu gizle"""
        if self.block_entity:
            self.block_entity.visible = False
    
    def show(self):
        """Bloğu göster"""
        if self.block_entity:
            self.block_entity.visible = True