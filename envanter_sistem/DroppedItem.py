# DroppedItem.py - Minecraft-style dropped item entity
from ursina import *
from ursina.shaders import unlit_shader
import time

class DroppedItem(Entity):
    """Yere düşmüş item entity - Minecraft tarzı döner ve toplanabilir"""
    def __init__(self, block_type, count, block_cells, atlas_texture, atlas_cols_total, atlas_rows, **kwargs):
        super().__init__(**kwargs)
        
        self.block_type = block_type
        self.count = count
        self.block_cells = block_cells
        self.atlas_texture = atlas_texture
        self.atlas_cols_total = atlas_cols_total
        self.atlas_rows = atlas_rows
        
        # 3D Blok modeli oluştur
        self.create_block_model()
        
        # Fizik
        self.velocity = Vec3(0, 0, 0)
        self.gravity = -20  # Yerçekimi
        self.on_ground = False
        self.bounce_factor = 0.3  # Zıplama katsayısı
        
        # Animasyon
        self.rotation_speed = 90  # Derece/saniye
        self.bob_speed = 2  # Yukarı-aşağı hareket hızı
        self.bob_amount = 0.1  # Yukarı-aşağı hareket miktarı
        self.spawn_time = time.time()
        
        # Toplama
        self.pickup_delay = 0.5  # İlk 0.5 saniye toplanamaz
        self.pickup_range = 2.0  # Toplama mesafesi
        self.magnet_range = 3.0  # Mıknatıs mesafesi (otomatik çekme)
        self.magnet_speed = 5.0
        
        # Ömür
        self.lifetime = 300  # 5 dakika (300 saniye)
        self.blink_start_time = 270  # Son 30 saniyede yanıp sönme
        
        # Collider
        self.collider = 'box'
        self.collision = True
    
    def create_block_model(self):
        """3D blok modeli oluştur"""
        vertices = []
        triangles = []
        uvs = []
        
        # Küp yüzleri
        faces_data = [
            # front (z-)
            [(0,0,0), (1,0,0), (1,1,0), (0,1,0)],
            # back (z+)
            [(1,0,1), (0,0,1), (0,1,1), (1,1,1)],
            # left (x-)
            [(0,0,1), (0,0,0), (0,1,0), (0,1,1)],
            # right (x+)
            [(1,0,0), (1,0,1), (1,1,1), (1,1,0)],
            # bottom (y-)
            [(0,0,1), (1,0,1), (1,0,0), (0,0,0)],
            # top (y+)
            [(0,1,0), (1,1,0), (1,1,1), (0,1,1)]
        ]
        
        face_names = ['front', 'back', 'left', 'right', 'bottom', 'top']
        idx = 0
        
        for face_idx, face_verts in enumerate(faces_data):
            # Vertex'leri ekle
            for v in face_verts:
                vertices.append(Vec3(v[0]-0.5, v[1]-0.5, v[2]-0.5))  # Merkeze al
            
            # Triangle'ları ekle
            triangles.extend([idx, idx+1, idx+2, idx, idx+2, idx+3])
            
            # UV'leri ekle
            ax, ay = self.block_cells[self.block_type][face_names[face_idx]]
            uv_coords = [
                (ax/self.atlas_cols_total, ay/self.atlas_rows),
                ((ax+1)/self.atlas_cols_total, ay/self.atlas_rows),
                ((ax+1)/self.atlas_cols_total, (ay+1)/self.atlas_rows),
                (ax/self.atlas_cols_total, (ay+1)/self.atlas_rows)
            ]
            uvs.extend(uv_coords)
            
            idx += 4
        
        # Mesh oluştur
        self.model = Mesh(vertices=vertices, triangles=triangles, uvs=uvs, mode='triangle')
        self.texture = self.atlas_texture
        self.shader = unlit_shader
        self.scale = 0.25  # Küçük boyut
    
    def update(self):
        """Her frame güncelleme"""
        dt = time.dt
        current_time = time.time()
        age = current_time - self.spawn_time
        
        # Ömür kontrolü
        if age > self.lifetime:
            destroy(self)
            return
        
        # Yanıp sönme (son 30 saniye)
        if age > self.blink_start_time:
            blink_speed = 5
            self.visible = int((age - self.blink_start_time) * blink_speed) % 2 == 0
        
        # Dönme animasyonu (Y ekseni etrafında)
        self.rotation_y += self.rotation_speed * dt
        
        # Yukarı-aşağı bob animasyonu (yerdeyken)
        if self.on_ground:
            # Yer hala var mı kontrol et (blok kırılmış olabilir)
            ground_check = self.check_ground_collision(self.position)
            if ground_check is None:
                # Yer yok - tekrar düşmeye başla
                self.on_ground = False
                self.velocity.y = 0
            else:
                # Yer var - bob animasyonu
                bob_offset = math.sin(age * self.bob_speed) * self.bob_amount
                self.y = self.ground_y + 0.125 + bob_offset  # 0.125 = yarı yükseklik
        else:
            # Havadayken fizik uygula
            self.velocity.y += self.gravity * dt
            
            # Yeni pozisyon hesapla
            new_pos = self.position + self.velocity * dt
            
            # Yatay çarpışma kontrolü (X ve Z eksenleri)
            new_pos, self.velocity = self.check_horizontal_collision(new_pos, self.velocity)
            
            # Dünya bloklarıyla çarpışma kontrolü (Y ekseni)
            ground_y = self.check_ground_collision(new_pos)
            
            if ground_y is not None:
                # Yere değdi
                new_pos.y = ground_y + 0.125  # 0.125 = item yarı yüksekliği
                self.ground_y = ground_y
                self.on_ground = True
                
                # Zıplama (ilk değmede)
                if self.velocity.y < 0:
                    self.velocity.y = -self.velocity.y * self.bounce_factor
                    if abs(self.velocity.y) < 0.5:  # Çok yavaşsa dur
                        self.velocity.y = 0
                        self.velocity.x *= 0.5
                        self.velocity.z *= 0.5
            
            self.position = new_pos
            
            # Yatay sürtünme
            self.velocity.x *= 0.98
            self.velocity.z *= 0.98
    
    def check_horizontal_collision(self, new_pos, velocity):
        """Yatay çarpışma kontrolü (X ve Z eksenleri)"""
        bounce = 0.4  # Sekme katsayısı
        
        # X ekseni kontrolü
        test_pos_x = Vec3(new_pos.x, self.position.y, self.position.z)
        hit_x = raycast(self.position, direction=(test_pos_x - self.position).normalized(), 
                       distance=0.3, ignore=[self])
        
        if hit_x.hit:
            # X ekseninde çarpışma - geri sek
            velocity.x = -velocity.x * bounce
            new_pos.x = self.position.x
        
        # Z ekseni kontrolü
        test_pos_z = Vec3(self.position.x, self.position.y, new_pos.z)
        hit_z = raycast(self.position, direction=(test_pos_z - self.position).normalized(), 
                       distance=0.3, ignore=[self])
        
        if hit_z.hit:
            # Z ekseninde çarpışma - geri sek
            velocity.z = -velocity.z * bounce
            new_pos.z = self.position.z
        
        return new_pos, velocity
    
    def check_ground_collision(self, pos):
        """Verilen pozisyonun altındaki blokları kontrol et"""
        # Item'ın altındaki pozisyonu kontrol et
        check_y = pos.y - 0.125  # Item'ın alt kısmı
        
        # Raycast ile aşağı doğru kontrol
        hit = raycast(pos, direction=Vec3(0, -1, 0), distance=0.5, ignore=[self])
        
        if hit.hit:
            # Çarpışma var - yüzeyin üstüne yerleştir
            return hit.world_point.y
        
        return None
    
    def check_pickup(self, player_pos, inventory):
        """Oyuncu yakınsa topla"""
        current_time = time.time()
        age = current_time - self.spawn_time
        
        # Pickup delay kontrolü
        if age < self.pickup_delay:
            return False
        
        distance = (self.position - player_pos).length()
        
        # Mıknatıs etkisi (otomatik çekme)
        if distance < self.magnet_range:
            direction = (player_pos - self.position).normalized()
            self.position += direction * self.magnet_speed * time.dt
        
        # Toplama mesafesi
        if distance < self.pickup_range:
            # Envantere ekle
            if inventory.add_block(self.block_type, self.count):
                # Toplama sesi çal (opsiyonel)
                # Audio('assets/sounds/pop.ogg', autoplay=True, volume=0.3)
                destroy(self)
                return True
        
        return False
