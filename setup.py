import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
	"packages": ["os", "json", "ctypes", "pyglet", "math", "random"],
	"include_files": [
		"data/", 
		"textures/", 
		"models/",
		"vert.glsl", "frag.glsl", 
		"overlay_vert.glsl", "overlay_frag.glsl",
		"inventory.json"
	]
}

setup(
	name = "PythonCraft Remake",
	version = "7.0",
	description = "Python Minecraft Clone",
	options = {"build_exe": build_exe_options},
	executables = [Executable("main.py", base="Win32GUI", target_name="PythonCraft.exe")]
)
