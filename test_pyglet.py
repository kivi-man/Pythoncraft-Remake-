
import pyglet
try:
    import pyglet.shapes
    print("pyglet.shapes available")
except ImportError:
    print("pyglet.shapes NOT available")
