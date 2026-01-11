
import pyglet.gl as gl
try:
    print("glColor4f:", gl.glColor4f)
except AttributeError:
    print("glColor4f not found")

try:
    print("glColor3f:", gl.glColor3f)
except AttributeError:
    print("glColor3f not found")

try:
    print("glOrtho:", gl.glOrtho)
except AttributeError:
    print("glOrtho not found")
