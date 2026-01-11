# MinecraftInventory.py
from ursina import *
from ursina.shaders import unlit_shader
from block_ekleme import CraftingRecipes

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
    def __init__(self, slot_type='normal', block_cells=None, atlas_texture=None, 
                 atlas_cols_total=None, atlas_rows=None, **kwargs):
        # Parent'ı kwargs'tan çıkar (eğer varsa)
        parent = kwargs.pop('parent', camera.ui)
        
        super().__init__(
            parent=parent,
            model='quad',
            color=color.rgba(50, 50, 50, 200),
            highlight_color=color.rgba(80, 80, 80, 200),
            pressed_color=color.rgba(40, 40, 40, 200),
            **kwargs
        )
        self.slot_type = slot_type  # 'normal', 'armor', 'offhand', 'crafting', 'output'
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
        
        # Slot tipi göstergesi (armor slotları için)
        self.slot_icon = None
        if slot_type == 'armor':
            self.slot_icon = Text(
                text="",
                parent=self,
                scale=2,
                origin=(0, 0),
                color=color.rgba(100, 100, 100, 150),
                position=(0, 0)
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


class MinecraftInventory:
    """Tam Minecraft-style envanter sistemi"""
    def __init__(self, block_cells, atlas_texture, atlas_cols_total, atlas_rows):
        self.block_cells = block_cells
        self.atlas_texture = atlas_texture
        self.atlas_cols_total = atlas_cols_total
        self.atlas_rows = atlas_rows
        
        self.menu_open = False
        self.selected_hotbar_index = 0
        
        # Drag-and-drop için
        self.dragged_item = None  # {'block_type': str, 'count': int}
        self.dragged_from_slot = None
        
        # --- HOTBAR (9 slots) ---
        self.hotbar_slots = []
        slot_width = 0.07
        slot_spacing = 0.01
        total_width = (slot_width + slot_spacing) * 9 - slot_spacing
        start_x = -total_width / 2
        
        for i in range(9):
            slot = InventorySlot(
                slot_type='normal',
                block_cells=block_cells,
                atlas_texture=atlas_texture,
                atlas_cols_total=atlas_cols_total,
                atlas_rows=atlas_rows,
                scale=(slot_width, slot_width),
                position=(start_x + i * (slot_width + slot_spacing), -0.45)
            )
            slot.index = i
            slot.on_click = lambda s=slot: self.on_slot_click(s)
            self.hotbar_slots.append(slot)
        
        # Hotbar seçim kenarlığı
        self.hotbar_selection = Entity(
            parent=camera.ui,
            model='cube',
            color=color.white,
            scale=(slot_width * 1.15, slot_width * 1.15, 0.01),
            z=0.01,
            position=self.hotbar_slots[0].position
        )
        
        # Seçili blok bilgisi
        self.info_text = Text(
            text="",
            parent=camera.ui,
            scale=1.5,
            origin=(0, 0),
            color=color.white,
            position=(0, -0.38),
            background=True
        )
        
        # --- TAM EKRAN ENVANTER MENÜSÜ ---
        self.menu_container = Entity(parent=camera.ui, enabled=False)
        
        # Arka plan
        self.background = Entity(
            parent=self.menu_container,
            model='quad',
            color=color.rgba(0, 0, 0, 150),
            scale=(2, 2),
            z=1
        )
        
        # Başlık
        self.title = Text(
            text="ENVANTER",
            parent=self.menu_container,
            scale=2,
            origin=(0, 0),
            color=color.white,
            position=(0, 0.45),
            z=-0.1
        )
        
        # --- ANA ENVANTER (27 slots = 3x9) ---
        self.main_inventory_slots = []
        slot_size = 0.065
        slot_gap = 0.008
        
        inv_start_x = -((slot_size + slot_gap) * 9 - slot_gap) / 2
        inv_start_y = 0.15
        
        for row in range(3):
            for col in range(9):
                slot = InventorySlot(
                    slot_type='normal',
                    block_cells=block_cells,
                    atlas_texture=atlas_texture,
                    atlas_cols_total=atlas_cols_total,
                    atlas_rows=atlas_rows,
                    parent=self.menu_container,
                    scale=(slot_size, slot_size),
                    position=(inv_start_x + col * (slot_size + slot_gap),
                             inv_start_y - row * (slot_size + slot_gap)),
                    z=-0.05
                )
                slot.index = row * 9 + col
                slot.on_click = lambda s=slot: self.on_slot_click(s)
                self.main_inventory_slots.append(slot)
        
        # --- HOTBAR KOPYASI (menüde) ---
        self.menu_hotbar_slots = []
        hotbar_y = inv_start_y - 3 * (slot_size + slot_gap) - 0.03
        
        for col in range(9):
            slot = InventorySlot(
                slot_type='normal',
                block_cells=block_cells,
                atlas_texture=atlas_texture,
                atlas_cols_total=atlas_cols_total,
                atlas_rows=atlas_rows,
                parent=self.menu_container,
                scale=(slot_size, slot_size),
                position=(inv_start_x + col * (slot_size + slot_gap), hotbar_y),
                z=-0.05
            )
            slot.index = col
            slot.on_click = lambda s=slot: self.on_slot_click(s)
            self.menu_hotbar_slots.append(slot)
        
        # --- ZIRH SLOTLARI (4 slots) ---
        self.armor_slots = []
        armor_icons = ["🪖", "👕", "👖", "👢"]  # Helmet, Chestplate, Leggings, Boots
        armor_x = inv_start_x - (slot_size + slot_gap) * 2.5
        armor_start_y = 0.15
        
        for i in range(4):
            slot = InventorySlot(
                slot_type='armor',
                block_cells=block_cells,
                atlas_texture=atlas_texture,
                atlas_cols_total=atlas_cols_total,
                atlas_rows=atlas_rows,
                parent=self.menu_container,
                scale=(slot_size, slot_size),
                position=(armor_x, armor_start_y - i * (slot_size + slot_gap)),
                z=-0.05
            )
            slot.slot_icon.text = armor_icons[i]
            slot.index = i
            slot.on_click = lambda s=slot: self.on_slot_click(s)
            self.armor_slots.append(slot)
        
        # --- OFFHAND SLOTU ---
        self.offhand_slot = InventorySlot(
            slot_type='offhand',
            block_cells=block_cells,
            atlas_texture=atlas_texture,
            atlas_cols_total=atlas_cols_total,
            atlas_rows=atlas_rows,
            parent=self.menu_container,
            scale=(slot_size, slot_size),
            position=(armor_x, armor_start_y - 4 * (slot_size + slot_gap) - 0.02),
            z=-0.05
        )
        self.offhand_slot.on_click = lambda: self.on_slot_click(self.offhand_slot)
        
        # --- CRAFTING GRID (2x2) ---
        self.crafting_slots = []
        craft_x = inv_start_x + (slot_size + slot_gap) * 9 + 0.05
        craft_y = 0.15
        
        for row in range(2):
            for col in range(2):
                slot = InventorySlot(
                    slot_type='crafting',
                    block_cells=block_cells,
                    atlas_texture=atlas_texture,
                    atlas_cols_total=atlas_cols_total,
                    atlas_rows=atlas_rows,
                    parent=self.menu_container,
                    scale=(slot_size, slot_size),
                    position=(craft_x + col * (slot_size + slot_gap),
                             craft_y - row * (slot_size + slot_gap)),
                    z=-0.05
                )
                slot.index = row * 2 + col
                slot.on_click = lambda s=slot: self.on_slot_click(s)
                self.crafting_slots.append(slot)
        
        # --- CRAFTING OUTPUT SLOTU ---
        self.crafting_output_slot = InventorySlot(
            slot_type='output',
            block_cells=block_cells,
            atlas_texture=atlas_texture,
            atlas_cols_total=atlas_cols_total,
            atlas_rows=atlas_rows,
            parent=self.menu_container,
            scale=(slot_size, slot_size),
            position=(craft_x + 2.5 * (slot_size + slot_gap), craft_y - 0.5 * (slot_size + slot_gap)),
            z=-0.05
        )
        # Crafting output için özel click handler
        self.crafting_output_slot.on_click = lambda: self.on_crafting_output_click()
        
        # Crafting ok işareti
        Text(
            text="→",
            parent=self.menu_container,
            scale=2.5,
            origin=(0, 0),
            color=color.white,
            position=(craft_x + 1.5 * (slot_size + slot_gap), craft_y - 0.5 * (slot_size + slot_gap)),
            z=-0.1
        )
        
        # Crafting başlık
        Text(
            text="CRAFTING",
            parent=self.menu_container,
            scale=1.2,
            origin=(0, 0),
            color=color.gray,
            position=(craft_x + (slot_size + slot_gap), craft_y + 0.05),
            z=-0.1
        )
        
        # Callback
        self.on_block_change = None
        self.on_item_drop = None  # Item drop callback
        
        # Crafting sistemi (block_ekleme.py'den)
        self.crafting_system = CraftingRecipes()
        
        # --- TOOLTIP SİSTEMİ ---
        self.tooltip = Entity(
            parent=camera.ui,
            model='quad',
            color=color.rgba(0, 0, 0, 220),
            scale=(0.25, 0.06),
            enabled=False,
            z=-0.2
        )
        self.tooltip_text = Text(
            parent=self.tooltip,
            text="",
            scale=1.6,
            origin=(0, 0),
            color=color.white,
            z=-0.01
        )
        self.tooltip_border = Entity(
            parent=self.tooltip,
            model='wireframe_cube',
            color=color.rgba(100, 150, 255, 255),
            scale=(1.05, 1.05, 0.1),
            z=0.01
        )
    
    def toggle_menu(self):
        """Menüyü aç/kapat"""
        self.menu_open = not self.menu_open
        self.menu_container.enabled = self.menu_open
        
        if self.menu_open:
            mouse.locked = False
            self.sync_hotbar_to_menu()
        else:
            mouse.locked = True
            self.sync_menu_to_hotbar()
    
    def sync_hotbar_to_menu(self):
        """Hotbar'ı menüdeki hotbar kopyasına senkronize et"""
        for i in range(9):
            self.menu_hotbar_slots[i].set_block(
                self.hotbar_slots[i].block_type,
                self.hotbar_slots[i].count
            )
    
    def sync_menu_to_hotbar(self):
        """Menüdeki hotbar kopyasını gerçek hotbar'a senkronize et"""
        for i in range(9):
            self.hotbar_slots[i].set_block(
                self.menu_hotbar_slots[i].block_type,
                self.menu_hotbar_slots[i].count
            )
        self.update_hotbar_info()
    
    def on_slot_click(self, slot):
        """Slot tıklama işlemi"""
        if not self.menu_open:
            return
        
        # Shift + Click - Hızlı transfer
        if held_keys['shift'] and mouse.left:
            if slot.block_type and slot.count > 0:
                # Hotbar'dan ana envantere
                if slot in self.hotbar_slots or slot in self.menu_hotbar_slots:
                    self.quick_transfer_to_main_inventory(slot)
                # Ana envanter'den hotbar'a
                elif slot in self.main_inventory_slots:
                    self.quick_transfer_to_hotbar(slot)
                # Crafting'den envantere
                elif slot in self.crafting_slots or slot == self.crafting_output_slot:
                    self.quick_transfer_to_inventory(slot)
            return
        
        # Sol tık - Sürükle/bırak
        if mouse.left:
            if self.dragged_item is None:
                # Slot'tan al
                if slot.block_type and slot.count > 0:
                    self.dragged_item = {
                        'block_type': slot.block_type,
                        'count': slot.count
                    }
                    self.dragged_from_slot = slot
                    slot.clear()
            else:
                # Slot'a bırak
                if slot.block_type is None:
                    # Boş slot'a bırak
                    slot.set_block(self.dragged_item['block_type'], self.dragged_item['count'])
                    self.dragged_item = None
                    self.dragged_from_slot = None
                elif slot.block_type == self.dragged_item['block_type']:
                    # Aynı tip - birleştir
                    slot.add_count(self.dragged_item['count'])
                    self.dragged_item = None
                    self.dragged_from_slot = None
                else:
                    # Farklı tip - takas
                    temp_type = slot.block_type
                    temp_count = slot.count
                    slot.set_block(self.dragged_item['block_type'], self.dragged_item['count'])
                    self.dragged_item = {'block_type': temp_type, 'count': temp_count}
                    self.dragged_from_slot = slot
                
                # Crafting kontrolü
                self.check_crafting()
        
        # Sağ tık - Stack'i böl
        elif mouse.right:
            if self.dragged_item is None:
                if slot.block_type and slot.count > 1:
                    half = slot.count // 2
                    self.dragged_item = {
                        'block_type': slot.block_type,
                        'count': half
                    }
                    slot.remove_count(half)
                    self.dragged_from_slot = slot
            else:
                # Tek tek bırak
                if slot.block_type is None or slot.block_type == self.dragged_item['block_type']:
                    if slot.block_type is None:
                        slot.set_block(self.dragged_item['block_type'], 1)
                    else:
                        slot.add_count(1)
                    
                    self.dragged_item['count'] -= 1
                    if self.dragged_item['count'] == 0:
                        self.dragged_item = None
                        self.dragged_from_slot = None
    
    def check_crafting(self):
        """Crafting grid'i kontrol et ve output'u güncelle"""
        # Crafting grid'deki itemleri al
        recipe = tuple(
            slot.block_type if slot.block_type else None
            for slot in self.crafting_slots
        )
        
        # "Craft olacak mı?" kontrolü
        if self.crafting_system.craft_olacak_mi(recipe, grid_size=2):
            # Craft sonucunu al
            result = self.crafting_system.get_craft_result(recipe, grid_size=2)
            if result:
                output_type, output_count = result
                self.crafting_output_slot.set_block(output_type, output_count)
        else:
            self.crafting_output_slot.clear()
    
    def on_crafting_output_click(self):
        """Crafting output slot'una tıklama - item'ı al ve crafting grid'i tüket"""
        if not self.menu_open:
            return
        
        # Output'ta bir şey var mı?
        if not self.crafting_output_slot.block_type or self.crafting_output_slot.count == 0:
            return
        
        # Sol tık - Output'u al
        if mouse.left:
            if self.dragged_item is None:
                # Output'u sürükle
                self.dragged_item = {
                    'block_type': self.crafting_output_slot.block_type,
                    'count': self.crafting_output_slot.count
                }
                self.dragged_from_slot = self.crafting_output_slot
                
                # Crafting grid'deki item'ları tüket (her slottan 1 adet)
                for slot in self.crafting_slots:
                    if slot.block_type is not None:
                        slot.remove_count(1)
                
                # Output'u temizle
                self.crafting_output_slot.clear()
                
                # Crafting'i yeniden kontrol et (belki hala aynı tarif yapılabilir)
                self.check_crafting()
            else:
                # Zaten bir şey sürüklüyoruz, output'a bırakmaya çalışıyoruz (izin verme)
                return
    
    def select_hotbar_slot(self, index):
        """Hotbar slot'u seç"""
        if 0 <= index < 9:
            self.selected_hotbar_index = index
            self.hotbar_selection.position = self.hotbar_slots[index].position
            self.update_hotbar_info()
    
    def update_hotbar_info(self):
        """Hotbar bilgi metnini güncelle"""
        slot = self.hotbar_slots[self.selected_hotbar_index]
        if slot.block_type and slot.count > 0:
            self.info_text.text = f"{slot.block_type.upper()} x{slot.count}"
            if self.on_block_change:
                self.on_block_change(slot.block_type)
        else:
            self.info_text.text = ""
            if self.on_block_change:
                self.on_block_change(None)
    
    def get_selected_block(self):
        """Seçili blok tipini döndür"""
        slot = self.hotbar_slots[self.selected_hotbar_index]
        return slot.block_type if slot.count > 0 else None
    
    def add_block(self, block_type, count=1):
        """Envantere blok ekle"""
        # Önce hotbar'da aynı tipte blok var mı kontrol et
        for slot in self.hotbar_slots:
            if slot.block_type == block_type:
                slot.add_count(count)
                self.update_hotbar_info()
                return True
        
        # Hotbar'da boş slot bul
        for slot in self.hotbar_slots:
            if slot.block_type is None:
                slot.set_block(block_type, count)
                self.update_hotbar_info()
                return True
        
        # Ana envanterde dene
        for slot in self.main_inventory_slots:
            if slot.block_type == block_type:
                slot.add_count(count)
                return True
        
        for slot in self.main_inventory_slots:
            if slot.block_type is None:
                slot.set_block(block_type, count)
                return True
        
        return False
    
    def remove_block(self, block_type=None, count=1):
        """Envanterten blok çıkar"""
        if block_type is None:
            slot = self.hotbar_slots[self.selected_hotbar_index]
            if slot.count > 0:
                slot.remove_count(count)
                self.update_hotbar_info()
                return True
        return False
    
    def has_block(self, block_type=None):
        """Belirtilen blok var mı kontrol et"""
        if block_type is None:
            slot = self.hotbar_slots[self.selected_hotbar_index]
            return slot.count > 0
        return False
    
    def handle_input(self, key):
        """Klavye girişlerini işle"""
        # E tuşu ile menü aç/kapat
        if key == 'e':
            self.toggle_menu()
            return True
        
        # Menü açıkken diğer kontrolleri devre dışı bırak
        if self.menu_open:
            # ESC ile menüyü kapat
            if key == 'escape':
                self.toggle_menu()
                return True
            
            # 1-9 tuşları - Hotbar swap (envanter açıkken)
            if key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
                index = int(key) - 1
                if self.dragged_item:
                    # Sürüklenen item varsa hotbar slot'una koy
                    target_slot = self.menu_hotbar_slots[index]
                    if target_slot.block_type is None:
                        target_slot.set_block(self.dragged_item['block_type'], self.dragged_item['count'])
                        self.dragged_item = None
                        self.dragged_from_slot = None
                    elif target_slot.block_type == self.dragged_item['block_type']:
                        target_slot.add_count(self.dragged_item['count'])
                        self.dragged_item = None
                        self.dragged_from_slot = None
                    else:
                        # Takas
                        temp_type = target_slot.block_type
                        temp_count = target_slot.count
                        target_slot.set_block(self.dragged_item['block_type'], self.dragged_item['count'])
                        self.dragged_item = {'block_type': temp_type, 'count': temp_count}
                return True
            
            return True
        
        # Q tuşu - Item drop (menü kapalıyken)
        if key == 'q':
            slot = self.hotbar_slots[self.selected_hotbar_index]
            if slot.block_type and slot.count > 0:
                # Ctrl basılı mı? (Tüm stack'i at)
                drop_count = slot.count if held_keys['control'] else 1
                
                # Drop callback'i çağır
                if self.on_item_drop:
                    self.on_item_drop(slot.block_type, drop_count)
                
                slot.remove_count(drop_count)
                self.update_hotbar_info()
            return True
        
        # Sayı tuşları (1-9) - Hotbar seçimi (menü kapalıyken)
        if key in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            index = int(key) - 1
            self.select_hotbar_slot(index)
            return True
        
        # Mouse wheel ile scroll
        if key == 'scroll up':
            prev_index = (self.selected_hotbar_index - 1) % 9
            self.select_hotbar_slot(prev_index)
            return True
        
        if key == 'scroll down':
            next_index = (self.selected_hotbar_index + 1) % 9
            self.select_hotbar_slot(next_index)
            return True
        
        return False
    
    def get_save_data(self):
        """Envanter verilerini kaydetmek için dict döndür"""
        data = {
            'selected_slot': self.selected_hotbar_index,
            'hotbar': [],
            'main_inventory': []
        }
        
        # Hotbar verilerini kaydet
        for slot in self.hotbar_slots:
            data['hotbar'].append({
                'block_type': slot.block_type,
                'count': slot.count
            })
        
        # Ana envanter verilerini kaydet
        for slot in self.main_inventory_slots:
            data['main_inventory'].append({
                'block_type': slot.block_type,
                'count': slot.count
            })
        
        return data
    
    def load_save_data(self, data):
        """Kaydedilmiş envanter verilerini yükle"""
        if not data:
            return
        
        # Seçili slot'u yükle
        if 'selected_slot' in data:
            self.select_hotbar_slot(data['selected_slot'])
        
        # Hotbar verilerini yükle
        if 'hotbar' in data:
            for i, slot_data in enumerate(data['hotbar']):
                if i < len(self.hotbar_slots):
                    if slot_data['block_type'] and slot_data['count'] > 0:
                        self.hotbar_slots[i].set_block(
                            slot_data['block_type'],
                            slot_data['count']
                        )
                    else:
                        self.hotbar_slots[i].clear()
        
        # Ana envanter verilerini yükle
        if 'main_inventory' in data:
            for i, slot_data in enumerate(data['main_inventory']):
                if i < len(self.main_inventory_slots):
                    if slot_data['block_type'] and slot_data['count'] > 0:
                        self.main_inventory_slots[i].set_block(
                            slot_data['block_type'],
                            slot_data['count']
                        )
                    else:
                        self.main_inventory_slots[i].clear()
        
        # Hotbar bilgisini güncelle
        self.update_hotbar_info()
    
    def update(self):
        """Her frame çağrılır - Tooltip için hover detection"""
        if self.menu_open:
            # Mouse hover detection
            hovered_slot = None
            all_slots = (self.hotbar_slots + self.menu_hotbar_slots + 
                        self.main_inventory_slots + self.armor_slots + 
                        self.crafting_slots + [self.crafting_output_slot, self.offhand_slot])
            
            for slot in all_slots:
                if slot.hovered and slot.block_type:
                    hovered_slot = slot
                    break
            
            if hovered_slot:
                # Tooltip göster
                self.tooltip.enabled = True
                
                # Blok ismini güzelleştir (grass -> Grass, oak_log -> Oak Log)
                block_name = hovered_slot.block_type.replace('_', ' ').title()
                self.tooltip_text.text = block_name
                
                if hovered_slot.count > 1:
                    self.tooltip_text.text += f" x{hovered_slot.count}"
                
                # Tooltip boyutunu metne göre ayarla
                text_width = len(self.tooltip_text.text) * 0.015
                self.tooltip.scale_x = max(0.15, text_width)
                
                # Mouse pozisyonuna göre yerleştir (sağ üst köşede)
                tooltip_x = mouse.x + 0.12
                tooltip_y = mouse.y + 0.05
                
                # Ekran dışına taşma kontrolü
                if tooltip_x + self.tooltip.scale_x / 2 > 0.95:
                    tooltip_x = mouse.x - 0.12
                if tooltip_y + self.tooltip.scale_y / 2 > 0.95:
                    tooltip_y = mouse.y - 0.05
                
                self.tooltip.position = (tooltip_x, tooltip_y)
            else:
                self.tooltip.enabled = False
        else:
            self.tooltip.enabled = False
    
    def quick_transfer_to_main_inventory(self, slot):
        """Hotbar'dan ana envantere hızlı transfer"""
        if not slot.block_type or slot.count == 0:
            return
        
        block_type = slot.block_type
        count = slot.count
        
        # Önce aynı tipte blok var mı bul
        for inv_slot in self.main_inventory_slots:
            if inv_slot.block_type == block_type:
                inv_slot.add_count(count)
                slot.clear()
                return
        
        # Boş slot bul
        for inv_slot in self.main_inventory_slots:
            if inv_slot.block_type is None:
                inv_slot.set_block(block_type, count)
                slot.clear()
                return
    
    def quick_transfer_to_hotbar(self, slot):
        """Ana envanter'den hotbar'a hızlı transfer"""
        if not slot.block_type or slot.count == 0:
            return
        
        block_type = slot.block_type
        count = slot.count
        
        # Önce menüdeki hotbar'da aynı tipte blok var mı bul
        for hotbar_slot in self.menu_hotbar_slots:
            if hotbar_slot.block_type == block_type:
                hotbar_slot.add_count(count)
                slot.clear()
                return
        
        # Boş slot bul
        for hotbar_slot in self.menu_hotbar_slots:
            if hotbar_slot.block_type is None:
                hotbar_slot.set_block(block_type, count)
                slot.clear()
                return
    
    def quick_transfer_to_inventory(self, slot):
        """Crafting'den envantere hızlı transfer"""
        if not slot.block_type or slot.count == 0:
            return
        
        block_type = slot.block_type
        count = slot.count
        
        # Önce hotbar'da dene
        for hotbar_slot in self.menu_hotbar_slots:
            if hotbar_slot.block_type == block_type:
                hotbar_slot.add_count(count)
                slot.clear()
                return
        
        for hotbar_slot in self.menu_hotbar_slots:
            if hotbar_slot.block_type is None:
                hotbar_slot.set_block(block_type, count)
                slot.clear()
                return
        
        # Ana envanterde dene
        for inv_slot in self.main_inventory_slots:
            if inv_slot.block_type == block_type:
                inv_slot.add_count(count)
                slot.clear()
                return
        
        for inv_slot in self.main_inventory_slots:
            if inv_slot.block_type is None:
                inv_slot.set_block(block_type, count)
                slot.clear()
                return
