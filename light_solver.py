import math
from collections import deque

class LightSolver:
	def __init__(self, world):
		self.world = world
		
		# Rule: Split Priority Queues
		self.high_priority_queue = deque() # For Block Break/Place
		self.low_priority_queue = deque()  # For Chunk Load / Sunlight Init
		
		# To ensure "Each block processing only ONCE per tick" (Rule 2)
		self.queued_locations = set()

		# Rule 3: Dirty Chunks Collection
		self.dirty_chunks = set()
		
		self.directions = [
			(1, 0, 0), (-1, 0, 0),
			(0, 1, 0), (0, -1, 0),
			(0, 0, 1), (0, 0, -1)
		]

	def add_to_queue(self, x, y, z, channel, priority='high'):
		if (x, y, z, channel) not in self.queued_locations:
			if priority == 'high':
				self.high_priority_queue.append((x, y, z, channel))
			else:
				self.low_priority_queue.append((x, y, z, channel))
			
			self.queued_locations.add((x, y, z, channel))

	def get_light(self, x, y, z, channel):
		# Optimized access
		if not self.world.is_position_loaded((x, y, z)):
			return 15 if channel == 1 else 0 # Boundary assumption: Sky is bright, Block is dark
		
		val = self.world.get_light((x, y, z))
		return val[channel]

	def set_light(self, x, y, z, val, channel):
		# Rule 4: Local Flood Fill (only loaded chunks)
		if not self.world.is_position_loaded((x, y, z)):
			return
			
		l_vals = list(self.world.get_light((x, y, z)))
		if l_vals[channel] != val:
			l_vals[channel] = val
			self.world.set_light((x, y, z), l_vals[0], l_vals[1])
			
			# Rule 3: Collect dirty chunks (don't update mesh yet)
			cp = self.world.get_chunk_position((x, y, z))
			self.dirty_chunks.add(cp)

	def toggle_light(self, position, old_block_type, new_block_type):
		"""
		Rule 1: Event-Driven Trigger
		"""
		x, y, z = position
		
		old_emit = old_block_type.light_level if old_block_type else 0
		new_emit = new_block_type.light_level if new_block_type else 0
		
		old_trans = old_block_type.transparent if old_block_type else True
		new_trans = new_block_type.transparent if new_block_type else True
		
		# Blocks always High Priority
		priority = 'high'
		
		# 1. Block Light Logic
		# Rule 5: Wake Neighbors on any change
		if old_emit != new_emit or old_trans != new_trans:
			self.add_to_queue(x, y, z, 0, priority)
			for dx, dy, dz in self.directions:
				self.add_to_queue(x+dx, y+dy, z+dz, 0, priority)
				
		# 2. Sky Light Logic
		# Rule 6: Column Based Updates
		if old_trans != new_trans:
			self.update_sky_column(x, y, z, new_trans, priority)
		
		# For Block Updates, we might want to process immediately a small batch?
		# But instructions say "Process Queue every tick: High then Low".
		pass

	def update_sky_column(self, x, y, z, is_transparent, priority='high'):
		# Rule 6: Sky Light Column Refresh
		# If a block acts as an obstruction (placing solid) or opening (breaking solid).
		
		# Check light above
		light_above = self.get_light(x, y+1, z, 1)
		
		if is_transparent:
			# Opening: If above is 15, we propagate down 15.
			if light_above == 15:
				# Propagate down efficiently
				cur_y = y
				while cur_y >= 0:
					if self.world.is_opaque_block((x, cur_y, z)):
						break
					
					self.set_light(x, cur_y, z, 15, 1)
					self.add_to_queue(x, cur_y, z, 1, priority) # Add to queue to spread sideways
					
					# Also wake neighbors of column to refill them
					for dx, dy, dz in self.directions:
						if dx == 0 and dz == 0: continue # Skip vertical neighbors
						self.add_to_queue(x+dx, cur_y+dy, z+dz, 1, priority)
						
					cur_y -= 1
			else:
				# Just wake self to calculate from neighbors
				self.add_to_queue(x, y, z, 1, priority)
				for dx, dy, dz in self.directions:
					self.add_to_queue(x+dx, y+dy, z+dz, 1, priority)

		else:
			# Closing/Obstruction
			# We blocked the light. 
			# The block itself is opaque, so light inside is 0 (handled by standard logic).
			# But blocks BELOW need to be updated.
			# They were likely 15 (if air). We need to wipe them or wake them.
			
			# We iterate down and "Darken" the column, letting neighbors refill it later if needed.
			cur_y = y - 1
			while cur_y >= 0:
				if self.world.is_opaque_block((x, cur_y, z)):
					break
				
				# If it was fully lit sky, it's now invalid. 
				# Set to 0 and let BFS refill it from sides if possible.
				if self.get_light(x, cur_y, z, 1) == 15:
					self.set_light(x, cur_y, z, 0, 1)
					self.add_to_queue(x, cur_y, z, 1, priority)
					
					# Wake neighbors to recalculate
					for dx, dy, dz in self.directions:
						self.add_to_queue(x+dx, cur_y+dy, z+dz, 1, priority)
				else:
					# If not 15, it might be correct or not, just wake it.
					self.add_to_queue(x, cur_y, z, 1, priority)
					
				cur_y -= 1
				
		# Wake self/neighbors for standard update
		self.add_to_queue(x, y, z, 1, priority)
		for dx, dy, dz in self.directions:
			self.add_to_queue(x+dx, y+dy, z+dz, 1, priority)

	def process_queue(self, budget=500):
		# Rule: Prioritize HIGH queue (Unlimited budget for interactivity)
		
		# 1. Process ALL High Priority Tasks (Responsiveness Guarantee)
		# Safety cap just in case of infinite loops, but realistically "unlimited"
		high_safety_limit = 10000 
		h_count = 0
		while self.high_priority_queue and h_count < high_safety_limit:
			x, y, z, channel = self.high_priority_queue.popleft()
			self.queued_locations.discard((x, y, z, channel))
			self.solve_node(x, y, z, channel, priority='high')
			h_count += 1
			
		# 2. Process LOW Priority Tasks (Budgeted)
		l_processed = 0
		# Resume budget usage where we left off? 
		# Or separate budgets? 
		# Let's say high priority is free, low is budgeted.
		
		while self.low_priority_queue and l_processed < budget:
			x, y, z, channel = self.low_priority_queue.popleft()
			self.queued_locations.discard((x, y, z, channel))
			self.solve_node(x, y, z, channel, priority='low')
			l_processed += 1
			
		# Process Dirty Chunks
		if h_count > 0 or l_processed > 0:
			self.update_dirty_chunks()
			
		# Return True if there is still WORK to be done (Low priority left)
		return len(self.low_priority_queue) > 0

	def solve_node(self, x, y, z, channel, priority='low'):
		if not self.world.is_position_loaded((x, y, z)):
			return
			
		# Calculate correct value based on surroundings (Automata Rule)
		current_val = self.get_light(x, y, z, channel)
		
		# 1. Emission (Self)
		emission = 0
		if channel == 0: # Block Light
			block_num = self.world.get_block_number((x, y, z))
			if block_num:
				bt = self.world.block_types[block_num]
				if bt: emission = bt.light_level
				
		# 2. Propagation (Neighbors)
		max_neighbor = 0
		for dx, dy, dz in self.directions:
			nx, ny, nz = x+dx, y+dy, z+dz
			
			n_light = self.get_light(nx, ny, nz, channel)
			
			# Rule 6 Logic Check: Sky propagation 15->15 down
			if channel == 1 and dy == 1 and n_light == 15: # If neighbor is ABOVE
				# Vertical sky propagation
				if n_light == 15:
					max_neighbor = max(max_neighbor, 16) # 16-1 = 15
					continue
			
			max_neighbor = max(max_neighbor, n_light)
		
		calculated_val = max_neighbor - 1
		calculated_val = max(calculated_val, emission)
		
		# Opacity check: If opaque, light is 0 (unless emission)
		if self.world.is_opaque_block((x, y, z)):
			calculated_val = emission # Emissive blocks can be opaque (e.g. Jack o Lantern)
		
		# Apply Constraints
		if calculated_val < 0: calculated_val = 0
		if calculated_val > 15: calculated_val = 15
		
		# Update Logic
		if current_val != calculated_val:
			self.set_light(x, y, z, calculated_val, channel)
			
			# Rule 5: Wake Neighbors
			for dx, dy, dz in self.directions:
				self.add_to_queue(x+dx, y+dy, z+dz, channel, priority)

	def update_dirty_chunks(self):
		# Collect valid chunk objects
		for cx, cy, cz in self.dirty_chunks:
			if (cx, cy, cz) in self.world.chunks:
				# Mark this chunk dirty
				self.world.mark_chunk_dirty((cx*16, cy*16, cz*16))
				# Mark neighbors? Usually mesh builds look at neighbors. 
				# Ideally yes.
				for dx, dy, dz in self.directions:
					self.world.mark_chunk_dirty(((cx+dx)*16, (cy+dy)*16, (cz+dz)*16))
					
		self.dirty_chunks.clear()

	def initialize_sunlight(self, chunk_position):
		# Initial sunlight fill logic
		# Rule 6: Column Logic applied to initialization
		cx, cy, cz = chunk_position
		base_x = cx * 16
		start_y = cy * 16
		end_y = start_y + 16
		base_z = cz * 16
		
		# Check above chunk
		above_loaded = self.world.is_position_loaded((base_x, end_y, base_z))
		
		for lx in range(16):
			for lz in range(16):
				gx, gy, gz = base_x + lx, end_y - 1, base_z + lz
				
				# Logic:
				# If above is load, check light.
				# If not loaded, assume 15.
				start_light = 0
				if not above_loaded:
					start_light = 15
				else:
					start_light = self.get_light(gx, end_y, gz, 1) # Get light at bottom of chunk above
				
				if start_light == 15:
					# Propagate 15 down manually through this new column
					cur_y = end_y - 1
					while cur_y >= start_y:
						if self.world.is_opaque_block((gx, cur_y, gz)):
							break
						self.set_light(gx, cur_y, gz, 15, 1)
						self.add_to_queue(gx, cur_y, gz, 1, 'low') # Add to spread sideways
						cur_y -= 1
				elif start_light > 0:
					# Propagate faded light
					self.set_light(gx, end_y-1, gz, start_light-1, 1)
					self.add_to_queue(gx, end_y-1, gz, 1, 'low')
		
		# Rule 5 (Sort of): Stitching
		# Add boundary blocks of loaded neighbors to queue
		neighbors = [
           (1, 0, 15, 0), (-1, 0, 0, 15),
           (0, 1, 15, 0), (0, -1, 0, 15)
        ] # (dx, dz, my_border, neig_border) logic simplified
		
		for dx, dz, _, _ in neighbors:
			ncx, ncz = cx + dx, cz + dz
			if self.world.is_position_loaded((ncx*16, 0, ncz*16)):
				pass
		
		# Trigger self & neighbor borders
		# Add the outer shell of this chunk to queue.
		for y in range(start_y, end_y):
			for i in range(16):
				# Front/Back/Left/Right faces
				self.add_to_queue(base_x + i, y, base_z, 1, 'low')
				self.add_to_queue(base_x + i, y, base_z + 15, 1, 'low')
				self.add_to_queue(base_x, y, base_z + i, 1, 'low')
				self.add_to_queue(base_x + 15, y, base_z + i, 1, 'low')
		
		# INCREMENTAL: Do not process immediately.

