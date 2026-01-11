import itertools

import itertools
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os

# Block ID Map (Loaded from blocks.mcpy)
BLOCK_MAP = {0: "Empty"}

def load_block_map():
	try:
		with open("data/blocks.mcpy", "r") as f:
			lines = f.readlines()
			
		for line in lines:
			line = line.strip()
			if not line or line.startswith("#"): continue
			
			if ":" in line:
				parts = line.split(":", 1)
				try:
					bid = int(parts[0].strip())
					props = parts[1]
					
					# simple parse for name "..."
					if 'name "' in props:
						start = props.find('name "') + 6
						end = props.find('"', start)
						if end != -1:
							name = props[start:end]
							BLOCK_MAP[bid] = name
				except:
					pass
	except Exception as e:
		print(f"Failed to load blocks.mcpy: {e}")
		# Fallback defaults
		BLOCK_MAP.update({
			1: "Stone", 2: "Grass", 3: "Dirt", 4: "Cobblestone", 5: "Planks", 7: "Bedrock", 
			17: "Log", 20: "Glass"
		})

load_block_map()

# Inverse map (Name -> ID)
# Handle duplicates? If multiple IDs have same name (e.g. Water), take first or last?
# Usually last overwrites.
NAME_TO_ID = {v: k for k, v in BLOCK_MAP.items()} 

# Sort names for dropdown
BLOCK_NAMES = sorted(list(BLOCK_MAP.values()))
if "Empty" in BLOCK_NAMES:
	BLOCK_NAMES.remove("Empty")
	BLOCK_NAMES.insert(0, "Empty")

RECIPE_FILE = "data/recipes.json"

class RecipeTool:
	def __init__(self, root):
		self.root = root
		self.root.title("Minecraft Clone Recipe Creator")
		
		self.inputs = []
		
		# Input Grid (2x2)
		input_frame = tk.LabelFrame(root, text="Input (2x2)", padx=10, pady=10)
		input_frame.pack(side="left", padx=10, pady=10)
		
		for r in range(2):
			for c in range(2):
				var = tk.StringVar(value="Empty")
				cb = ttk.Combobox(input_frame, textvariable=var, values=BLOCK_NAMES, state="readonly")
				cb.grid(row=r, column=c, padx=5, pady=5)
				self.inputs.append(var)
		
		# Options
		self.shapeless_var = tk.BooleanVar()
		tk.Checkbutton(input_frame, text="Random Pattern (Shapeless)", variable=self.shapeless_var).grid(row=2, column=0, columnspan=2)
				
		# Arrow
		tk.Label(root, text="->", font=("Arial", 20)).pack(side="left")
		
		# Output
		output_frame = tk.LabelFrame(root, text="Output", padx=10, pady=10)
		output_frame.pack(side="left", padx=10, pady=10)
		
		self.out_var = tk.StringVar(value="Wood Planks")
		ttk.Combobox(output_frame, textvariable=self.out_var, values=BLOCK_NAMES, state="readonly").pack()
		
		tk.Label(output_frame, text="Count:").pack()
		self.out_count = tk.Spinbox(output_frame, from_=1, to=64, width=5)
		self.out_count.pack()
		
		# Save Button
		tk.Button(root, text="Save Recipe", command=self.save_recipe, bg="#DDFFDD", height=2).pack(side="bottom", fill="x", padx=20, pady=20)
		
		# Load existing just to check count
		self.existing_recipes = []
		self.load_recipes()

	def load_recipes(self):
		if os.path.exists(RECIPE_FILE):
			try:
				with open(RECIPE_FILE, "r") as f:
					self.existing_recipes = json.load(f)
			except:
				self.existing_recipes = []

	def save_recipe(self):
		# Collect Inputs
		input_ids = []
		for var in self.inputs:
			name = var.get()
			bid = NAME_TO_ID.get(name, 0)
			input_ids.append(bid)
			
		# Collect Output
		out_name = self.out_var.get()
		out_id = NAME_TO_ID.get(out_name, 0)
		
		try:
			count = int(self.out_count.get())
		except:
			count = 1
			
		if out_id == 0:
			messagebox.showerror("Error", "Output cannot be Empty")
			return

		recipes_to_add = []

		if self.shapeless_var.get():
			# Generate all permutations
			# input_ids has 4 elements.
			unique_perms = set(itertools.permutations(input_ids))
			
			for perm in unique_perms:
				# perm is tuple, convert to list
				recipes_to_add.append({
					"input": list(perm),
					"output": {"id": out_id, "count": count}
				})
			print(f"Generated {len(recipes_to_add)} variations.")
		else:
			# Single pattern
			recipes_to_add.append({
				"input": input_ids,
				"output": {"id": out_id, "count": count}
			})
		
		# Add and Save
		count_added = 0
		for r in recipes_to_add:
			# Check duplicate logic could go here, but for now allow
			self.existing_recipes.append(r)
			count_added += 1
		
		try:
			os.makedirs("data", exist_ok=True)
			with open(RECIPE_FILE, "w") as f:
				json.dump(self.existing_recipes, f, indent=4)
			messagebox.showinfo("Success", f"Saved {count_added} Recipes!")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to save: {e}")

if __name__ == "__main__":
	root = tk.Tk()
	app = RecipeTool(root)
	root.mainloop()
