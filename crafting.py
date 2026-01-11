import json
import os

class RecipeManager:
	def __init__(self):
		self.recipes = []
		self.load_recipes()

	def load_recipes(self, filename="data/recipes.json"):
		if not os.path.exists(filename):
			# Create default if missing
			self.save_default_recipes(filename)
			return

		try:
			with open(filename, "r") as f:
				self.recipes = json.load(f)
			print(f"Loaded {len(self.recipes)} crafting recipes.")
		except Exception as e:
			print(f"Failed to load recipes: {e}")

	def save_default_recipes(self, filename):
		# Default: 1 Log (7) -> 4 Wood (5) - Simplest recipe
		# Assuming Log ID 7, Wood ID 5.
		# Format: input: [TL, TR, BL, BR], output: {id: X, count: Y}
		default_data = [
			{
				"input": [7, 0, 0, 0], # Log in Top-Left
				"output": {"id": 5, "count": 4}
			},
			{
				"input": [0, 7, 0, 0], # Log in Top-Right
				"output": {"id": 5, "count": 4}
			},
			{
				"input": [0, 0, 7, 0], # Log in Bottom-Left
				"output": {"id": 5, "count": 4}
			},
			{
				"input": [0, 0, 0, 7], # Log in Bottom-Right
				"output": {"id": 5, "count": 4}
			}
		]
		
		# Ensure dir exists
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		
		with open(filename, "w") as f:
			json.dump(default_data, f, indent=4)
		
		self.recipes = default_data

	def check_recipe(self, grid_items):
		# grid_items: List of 4 or 9 InventoryItems (or None).
		
		# Extract IDs
		input_ids = []
		for item in grid_items:
			if item:
				input_ids.append(item.block_type)
			else:
				input_ids.append(0) # 0 for empty
				
		# Check against recipes
		for recipe in self.recipes:
			r_input = recipe["input"]
			if r_input == input_ids:
				# Match!
				out = recipe["output"]
				return out["id"], out["count"]
				
		return None, 0
