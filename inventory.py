import json
import os
import crafting

class InventoryItem:
	def __init__(self, block_type, count=1):
		self.block_type = block_type
		self.count = count
	
	def to_dict(self):
		return {"block_type": self.block_type, "count": self.count}
	
	@staticmethod
	def from_dict(data):
		if data is None: return None
		return InventoryItem(data["block_type"], data["count"])

class Inventory:
	def __init__(self):
		# 9 Hotbar slots
		self.hotbar = [None] * 9
		# 27 Main Inventory slots
		self.main_inventory = [None] * 27
		
		# Crafting (3x3)
		self.crafting_grid = [None] * 9
		self.crafting_output = None
		self.crafting_size = 2 # 2 for 2x2 (Inventory), 3 for 3x3 (Crafting Table)
		
		self.recipe_manager = crafting.RecipeManager()
		
		self.selected_hotbar_index = 0
		
	def select_slot(self, index):
		if 0 <= index < 9:
			self.selected_hotbar_index = index
			
	def get_selected_block(self):
		item = self.hotbar[self.selected_hotbar_index]
		if item:
			return item.block_type
		return None

	def get_selected_item(self):
		return self.hotbar[self.selected_hotbar_index]

	def consume_held_item(self, count=1):
		item = self.hotbar[self.selected_hotbar_index]
		if item:
			item.count -= count
			if item.count <= 0:
				self.hotbar[self.selected_hotbar_index] = None
			self.save() # Auto-save
			return True
		return False
		
	# OLD add_item removed from here

	def update_crafting_output(self):
		num_slots = self.crafting_size * self.crafting_size
		out_id, out_count = self.recipe_manager.check_recipe(self.crafting_grid[:num_slots])
		if out_id:
			self.crafting_output = InventoryItem(out_id, out_count)
		else:
			self.crafting_output = None

	def craft(self):
		# Called when output is picked up
		# Consumes 1 from each populated crafting slot
		for i in range(len(self.crafting_grid)):
			if self.crafting_grid[i]:
				self.crafting_grid[i].count -= 1
				if self.crafting_grid[i].count <= 0:
					self.crafting_grid[i] = None
		self.update_crafting_output()
		self.save() # Auto-save

	def save(self, filename="inventory.json"):
		data = {
			"hotbar": [item.to_dict() if item else None for item in self.hotbar],
			"main": [item.to_dict() if item else None for item in self.main_inventory],
			"crafting": [item.to_dict() if item else None for item in self.crafting_grid]
		}
		try:
			with open(filename, "w") as f:
				json.dump(data, f)
			# print("Inventory saved.") # Comment out to avoid spam
		except Exception as e:
			print(f"Failed to save inventory: {e}")

	def load(self, filename="inventory.json"):
		if not os.path.exists(filename):
			return
		try:
			with open(filename, "r") as f:
				data = json.load(f)
				
			self.hotbar = [InventoryItem.from_dict(item) for item in data.get("hotbar", [])]
			while len(self.hotbar) < 9: self.hotbar.append(None)
			
			self.main_inventory = [InventoryItem.from_dict(item) for item in data.get("main", [])]
			while len(self.main_inventory) < 27: self.main_inventory.append(None)
			
			self.crafting_grid = [InventoryItem.from_dict(item) for item in data.get("crafting", [])]
			while len(self.crafting_grid) < 9: self.crafting_grid.append(None)
			
			# Check recipe after load
			self.update_crafting_output()
			
			print("Inventory loaded.")
		except Exception as e:
			print(f"Failed to load inventory: {e}")

	def add_item(self, item):
		# Tries to add item to hotbar then main inventory
		# Returns remaining count
		start_count = item.count
		
		# 1. Try to stack
		for slot_list in [self.hotbar, self.main_inventory]:
			for existing in slot_list:
				if existing and existing.block_type == item.block_type:
					# Simple stack unlimited for now or limit 64?
					can_add = 64 - existing.count
					if can_add > 0:
						to_add = min(item.count, can_add)
						existing.count += to_add
						item.count -= to_add
						if item.count <= 0: 
							self.save() # Auto-save on success
							return 0
		
		# 2. Try empty slots
		for slot_list in [self.hotbar, self.main_inventory]:
			for i in range(len(slot_list)):
				if slot_list[i] is None:
					slot_list[i] = InventoryItem(item.block_type, item.count)
					item.count = 0
					self.save() # Auto-save
					return 0
		
		if item.count < start_count:
			self.save() # Save partial add
			
		return item.count # Failed to add all

