# Tree.py
import random

def generate_tree(world, x, y, z,
                  min_height=4, max_height=7,
                  leaf_radius=2, leaf_density=0.8):
    """
    Minecraft tarzı basit meşe ağacı üretir.
    
    world: ChunkedVoxelWorld
    (x,y,z): kök koordinat
    min_height, max_height: gövde yüksekliği
    leaf_radius: yaprak yarıçapı
    leaf_density: yaprak olasılığı (0.0 - 1.0)
    """
    height = random.randint(min_height, max_height)

    # --- Gövde (oak) ---
    for i in range(height):
        world.add_block((x, y+i, z), 'oak')

    # --- Yapraklar (oak_leaves) ---
    top_y = y + height
    for dy in range(-leaf_radius, leaf_radius+1):
        for dx in range(-leaf_radius, leaf_radius+1):
            for dz in range(-leaf_radius, leaf_radius+1):
                dist = abs(dx) + abs(dy) + abs(dz)

                # Küp yerine daha doğal küresel hacim
                if dist <= leaf_radius + 1:
                    # Tepede daha sık yaprak
                    chance = leaf_density if dy <= 0 else 1.0
                    if random.random() < chance:
                        bx, by, bz = x+dx, top_y+dy, z+dz
                        # Gövdenin tam ortasına yaprak koyma
                        if not (dx == 0 and dz == 0 and dy <= 0):
                            world.add_block((bx, by, bz), 'oak_leaves')
