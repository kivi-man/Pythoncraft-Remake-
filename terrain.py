import random
from noise import pnoise2
from Tree import generate_tree
import chunk

def generate_terrain(world, size_x=64, size_z=64, max_height=16, scale=30, seed=None, offset=(0,0), sea_level=6):
    if seed is None:
        seed = random.randint(0, 10000)

    ox, oz = offset
    sand_level = sea_level  # Kum seviyesi

    for x in range(size_x):
        for z in range(size_z):
            world_x = ox + x
            world_z = oz + z

            height = int(pnoise2((world_x+seed)/scale,
                                 (world_z+seed)/scale,
                                 octaves=4) * max_height/2 + max_height/2)
            if height < 1: height = 1

            for y in range(height):
                if y == 0:
                    block = 'bedrock'
                elif y < height - 4:
                    block = 'stone'
                elif y < height - 1:
                    block = 'dirt' if height > sand_level else 'sand'
                else:
                    block = 'grass' if height > sand_level else 'sand'

                world.add_block((world_x, y, world_z), block)

            # Üst blok çimen veya kum olsa bile water ekleme
            for y in range(height, sea_level + 1):  # su seviyesi
                world.add_block((world_x, y, world_z), 'water')

            # Rastgele ağaç
            top_y = height - 1
            if block == 'grass' and random.random() < 0.03:
                generate_tree(world, world_x, top_y+1, world_z)


def generate_chunk(world, cpos, seed=0, max_height=16, scale=30, sea_level=6):
    cx, cy, cz = cpos
    if cy != 0:
        return

    start_x = cx * chunk.CHUNK_SIZE
    start_z = cz * chunk.CHUNK_SIZE

    sand_level = sea_level

    for x in range(start_x, start_x + chunk.CHUNK_SIZE):
        for z in range(start_z, start_z + chunk.CHUNK_SIZE):
            height = int(pnoise2((x+seed)/scale,
                                 (z+seed)/scale,
                                 octaves=4) * max_height/2 + max_height/2)
            if height < 1: height = 1

            for y in range(height):
                if y == 0:
                    block = 'bedrock'
                elif y < height - 4:
                    block = 'stone'
                elif y < height - 1:
                    block = 'dirt' if height > sand_level else 'sand'
                else:
                    block = 'grass' if height > sand_level else 'sand'

                world.add_block((x, y, z), block)

            # Çimen veya kum üstüne kadar water ekleme
            for y in range(height, sea_level + 1):
                world.add_block((x, y, z), 'water')

            # Rastgele ağaç
            top_y = height - 1
            if block == 'grass' and height > 4 and random.random() < 0.03:
                generate_tree(world, x, top_y+1, z)
