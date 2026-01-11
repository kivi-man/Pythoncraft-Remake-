#version 330

out vec4 fragment_colour;

uniform sampler2DArray texture_array_sampler;
uniform float alpha_factor;

in vec3 local_position;
in vec3 interpolated_tex_coords;
in float interpolated_shading_value;

void main(void) {
	vec4 texture_colour = texture(texture_array_sampler, interpolated_tex_coords);
	
	// Apply alpha factor to the texture alpha
	float alpha = texture_colour.a * alpha_factor;
	
	fragment_colour = vec4(texture_colour.rgb * interpolated_shading_value, alpha);

	if (alpha == 0.0) { // discard if texel's alpha component is 0 (texel is transparent)
		discard;
	}
}