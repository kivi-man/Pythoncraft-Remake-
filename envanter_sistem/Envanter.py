# Envanter.py
from ursina import *
from ursina.shaders import unlit_shader

class Block3D(Entity):
    """Envanter içinde gösterilecek 3D blok modeli"""
    def __init__(self, block_type, block_cells, atlas_texture, atlas_cols_total, atlas_rows, **kwargs):
        super().__init__(**kwargs)
        
        # Blok mesh'i oluştur
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
            ax, ay = block_cells[block_type][face_names[face_idx]]
            uv_coords = [
                (ax/atlas_cols_total, ay/atlas_rows),
                ((ax+1)/atlas_cols_total, ay/atlas_rows),
                ((ax+1)/atlas_cols_total, (ay+1)/atlas_rows),
                (ax/atlas_cols_total, (ay+1)/atlas_rows)
            ]
            uvs.extend(uv_coords)
            
            idx += 4
        
        # Mesh oluştur
        self.model = Mesh(vertices=vertices, triangles=triangles, uvs=uvs, mode='triangle')
        self.texture = atlas_texture
        self.shader = unlit_shader
        self.rotation_y = 45
        self.rotation_x = 20


class InventorySlot(Button):
    """Envanter slot'u - 3D blok ve miktar gösterir"""
    def __init__(self, index, block_cells, atlas_texture, atlas_cols_total, atlas_rows, **kwargs):
        super().__init__(
            parent=camera.ui,
            model='quad',
            color=color.rgba(50, 50, 50, 200),
            highlight_color=color.rgba(80, 80, 80, 200),
            pressed_color=color.rgba(40, 40, 40, 200),
            scale=(0.06, 0.06),
            **kwargs
        )
        self.index = index
        self.block_type = None
        self.count = 0
        self.block_cells = block_cells
        self.atlas_texture = atlas_texture
        self.atlas_cols_total = atlas_cols_total
        self.atlas_rows = atlas_rows
        
        # 3D Blok modeli
        self.block_3d = None
        
        # Miktar etiketi
        self.count_text = Text(
            text="",
            parent=self,
            scale=1.8,
            origin=(0.5, -0.5),
            color=color.white,
            position=(0.35, -0.35)
        )
        
        # Seçili kenarlık
        self.selection_border = Entity(
            parent=self,
            model='cube',
            color=color.white,
            scale=(1.15, 1.15, 0.01),
            z=0.01,
            visible=False
        )
    
    def set_block(self, block_type, count=1):
        """Slot'a blok ekle"""
        self.block_type = block_type
        self.count = count
        self.update_display()
    
    def add_count(self, amount=1):
        """Miktar ekle"""
        self.count += amount
        self.update_display()
    
    def remove_count(self, amount=1):
        """Miktar çıkar"""
        self.count = max(0, self.count - amount)
        if self.count == 0:
            self.clear()
        else:
            self.update_display()
    
    def clear(self):
        """Slot'u temizle"""
        self.block_type = None
        self.count = 0
        self.update_display()
    
    def update_display(self):
        """Görüntüyü güncelle"""
        # Eski 3D bloğu sil
        if self.block_3d:
            destroy(self.block_3d)
            self.block_3d = None
        
        if self.block_type and self.count > 0:
            # 3D blok oluştur
            self.block_3d = Block3D(
                self.block_type,
                self.block_cells,
                self.atlas_texture,
                self.atlas_cols_total,
                self.atlas_rows,
                parent=self,
                scale=0.35,
                z=-0.1
            )
            
            self.count_text.text = str(self.count) if self.count > 1 else ""
            self.color = color.rgba(70, 70, 70, 200)
        else:
            self.count_text.text = ""
            self.color = color.rgba(50, 50, 50, 200)
    
    def set_selected(self, selected):
        """Seçili durumu ayarla"""
        self.selection_border.visible = selected
        if selected:
            self.color = color.rgba(90, 90, 90, 220)
        else:
            self.color = color.rgba(70, 70, 70, 200) if self.block_type else color.rgba(50, 50, 50, 200)


class FullInventoryMenu(Entity):
    """Tam ekran envanter menüsü (E tuşu ile açılır)"""
    def __init__(self, block_cells, atlas_texture, atlas_cols_total, atlas_rows, **kwargs):
        super().__init__(parent=camera.ui)
        self.block_cells = block_cells
        self.atlas_texture = atlas_texture
        self.atlas_cols_total = atlas_cols_total
        self.atlas_rows = atlas_rows
        
        # Arka plan
        self.background = Entity(
            parent=self,
            model='quad',
            color=color.rgba(0, 0, 0, 150),
            scale=(2, 2),
            z=1
        )
        
        # Başlık
        self.title = Text(
            text="ENVANTER",
            parent=self,
            scale=2,
            origin=(0, 0),
            color=color.white,
            position=(0, 0.42),
            z=-0.1
        )
        
        # Slot'lar (9x4 = 36 slot)
        self.slots = []
        rows = 4
        cols = 9
        slot_size = 0.08
        slot_spacing = 0.01
        
        start_x = -(cols * (slot_size + slot_spacing) - slot_spacing) / 2
        start_y = 0.3
        
        for row in range(rows):
            for col in range(cols):
                slot = Button(
                    parent=self,
                    model='quad',
                    color=color.rgba(50, 50, 50, 200),
                    scale=(slot_size, slot_size),
                    position=(start_x + col * (slot_size + slot_spacing),
                             start_y - row * (slot_size + slot_spacing)),
                    z=-0.05
                )
                slot.block_type = None
                slot.count = 0
                slot.block_3d = None
                slot.index = row * cols + col
                
                # Miktar text
                slot.count_text = Text(
                    text="",
                    parent=slot,
                    scale=1.5,
                    origin=(0.5, -0.5),
                    color=color.white,
                    position=(0.35, -0.35)
                )
                
                self.slots.append(slot)
        
        # Hotbar ayrımı çizgisi
        Entity(
            parent=self,
            model='quad',
            color=color.white,
            scale=(cols * (slot_size + slot_spacing), 0.003),
            position=(0, start_y - 3 * (slot_size + slot_spacing) - slot_spacing),
            z=-0.05
        )
        
        # Hotbar etiketi
        Text(
            text="HOTBAR",
            parent=self,
            scale=1.2,
            origin=(0, 0),
            color=color.gray,
            position=(0, start_y - 3 * (slot_size + slot_spacing) - 0.04),
            z=-0.1
        )
        
        # Başlangıçta gizli
        self.enabled = False
    
    def update_slot(self, index, block_type, count):
        """Slot'u güncelle"""
        if 0 <= index < len(self.slots):
            slot = self.slots[index]
            
            # Eski 3D bloğu sil
            if slot.block_3d:
                destroy(slot.block_3d)
                slot.block_3d = None
            
            slot.block_type = block_type
            slot.count = count
            
            if block_type and count > 0:
                # 3D blok oluştur
                slot.block_3d = Block3D(
                    block_type,
                    self.block_cells,
                    self.atlas_texture,
                    self.atlas_cols_total,
                    self.atlas_rows,
                    parent=slot,
                    scale=0.45,
                    z=-0.1
                )
                slot.count_text.text = str(count) if count > 1 else ""
                slot.color = color.rgba(70, 70, 70, 200)
            else:
                slot.count_text.text = ""
                slot.color = color.rgba(50, 50, 50, 200)
    
    def show(self):
        """Menüyü göster"""
        self.enabled = True
        mouse.locked = False
    
    def hide(self):
        """Menüyü gizle"""
        self.enabled = False
        mouse.locked = True


class Inventory:
    """Envanter sistemi - 9 slot hotbar + tam ekran menü"""
    def __init__(self, block_cells, atlas_texture, atlas_cols_total, atlas_rows, slot_count=9):
        self.slot_count = slot_count
        self.slots = []
        self.selected_index = 0
        self.visible = True
        self.block_cells = block_cells
        self.atlas_texture = atlas_texture
        self.atlas_cols_total = atlas_cols_total
        self.atlas_rows = atlas_rows
        
        # Hotbar slot'ları oluştur
        slot_width = 0.07
        slot_spacing = 0.01
        total_width = (slot_width + slot_spacing) * slot_count - slot_spacing
        start_x = -total_width / 2
        
        for i in range(slot_count):
            slot = InventorySlot(
                index=i,
                block_cells=block_cells,
                atlas_texture=atlas_texture,
                atlas_cols_total=atlas_cols_total,
                atlas_rows=atlas_rows,
                position=(start_x + i * (slot_width + slot_spacing), -0.45)
            )
            self.slots.append(slot)
        
        # İlk slot'u seçili yap
        self.slots[0].set_selected(True)
        
        # Bilgi metni (seçili blok adı)
        self.info_text = Text(
            text="",
            parent=camera.ui,
            scale=1.5,
            origin=(0, 0),
            color=color.white,
            position=(0, -0.38),
            background=True
        )
        
        # Tam ekran envanter menüsü
        self.full_menu = FullInventoryMenu(
            block_cells=block_cells,
            atlas_texture=atlas_texture,
            atlas_cols_total=atlas_cols_total,
            atlas_rows=atlas_rows
        )
        self.menu_open = False
    
    def select_slot(self, index):
        """Slot seç"""
        if 0 <= index < self.slot_count:
            self.slots[self.selected_index].set_selected(False)
            self.selected_index = index
            self.slots[self.selected_index].set_selected(True)
            self.update_info()
    
    def get_selected_block(self):
        """Seçili blok tipini döndür"""
        slot = self.slots[self.selected_index]
        return slot.block_type if slot.count > 0 else None
    
    def add_block(self, block_type, count=1):
        """Envantere blok ekle"""
        # Önce hotbar'da aynı tipte blok var mı kontrol et
        for slot in self.slots:
            if slot.block_type == block_type:
                slot.add_count(count)
                self.update_info()
                self.sync_menu()
                return True
        
        # Hotbar'da boş slot bul
        for slot in self.slots:
            if slot.block_type is None:
                slot.set_block(block_type, count)
                self.update_info()
                self.sync_menu()
                return True
        
        # Envanter dolu
        return False
    
    def remove_block(self, block_type=None, count=1):
        """Envanterten blok çıkar (None ise seçili slot'tan)"""
        if block_type is None:
            slot = self.slots[self.selected_index]
            if slot.count > 0:
                slot.remove_count(count)
                self.update_info()
                self.sync_menu()
                return True
        else:
            for slot in self.slots:
                if slot.block_type == block_type and slot.count > 0:
                    slot.remove_count(count)
                    self.update_info()
                    self.sync_menu()
                    return True
        return False
    
    def has_block(self, block_type=None):
        """Belirtilen blok var mı kontrol et (None ise seçili slot)"""
        if block_type is None:
            slot = self.slots[self.selected_index]
            return slot.count > 0
        else:
            for slot in self.slots:
                if slot.block_type == block_type and slot.count > 0:
                    return True
        return False
    
    def update_info(self):
        """Bilgi metnini güncelle"""
        slot = self.slots[self.selected_index]
        if slot.block_type and slot.count > 0:
            self.info_text.text = f"{slot.block_type.upper()} x{slot.count}"
        else:
            self.info_text.text = ""
    
    def toggle_visibility(self):
        """Hotbar'ı göster/gizle"""
        self.visible = not self.visible
        for slot in self.slots:
            slot.visible = self.visible
        self.info_text.visible = self.visible
    
    def toggle_menu(self):
        """Tam ekran menüyü aç/kapat"""
        self.menu_open = not self.menu_open
        if self.menu_open:
            self.sync_menu()
            self.full_menu.show()
        else:
            self.full_menu.hide()
    
    def sync_menu(self):
        """Hotbar'ı tam ekran menü ile senkronize et"""
        if self.menu_open:
            # İlk 9 slot hotbar (en alt satır)
            for i in range(self.slot_count):
                slot = self.slots[i]
                menu_index = 27 + i  # Son satır (4. satır)
                self.full_menu.update_slot(menu_index, slot.block_type, slot.count)
    
    def handle_input(self, key):
        """Klavye girişlerini işle"""
        # E tuşu ile menü aç/kapat
        if key == 'e':
            self.toggle_menu()
            return True
        
        # Menü açıkken diğer kontrolleri devre dışı bırak
        if self.menu_open:
            return True
        
        # Sayı tuşları (1-9)
        if key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            index = int(key) - 1
            if index < self.slot_count:
                self.select_slot(index)
                return True
        
        # Mouse wheel ile scroll
        if key == 'scroll up':
            prev_index = (self.selected_index - 1) % self.slot_count
            self.select_slot(prev_index)
            return True
        
        if key == 'scroll down':
            next_index = (self.selected_index + 1) % self.slot_count
            self.select_slot(next_index)
            return True
        
        return False
    
    def get_slot_count(self, block_type):
        """Belirtilen blok tipinden kaç tane olduğunu döndür"""
        total = 0
        for slot in self.slots:
            if slot.block_type == block_type:
                total += slot.count
        return total
    
    def clear_all(self):
        """Tüm envanteri temizle"""
        for slot in self.slots:
            slot.clear()
        self.update_info()
        self.sync_menu()