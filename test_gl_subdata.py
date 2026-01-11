
import pyglet.gl as gl
try:
    print("glBufferSubData:", gl.glBufferSubData)
except AttributeError:
    print("glBufferSubData not found")
