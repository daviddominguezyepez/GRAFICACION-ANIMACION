import moderngl
import moderngl_window as mglw
from moderngl_window import geometry
import glm
import random
import math
import numpy as np

63
class SynthwaveDrive(mglw.WindowConfig):
    title = "CYBERPUNK CITY"
    window_size = (1280, 720)
    aspect_ratio = 16 / 9
    resizable = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.ctx.enable(moderngl.DEPTH_TEST)

        self.cam_yaw   = 0.0
        self.cam_zoom  = 0.0
        self.cam_height = 0.0
        self.keys_held = set()

        # Cache de view-projection por frame
        self._vp_cache = None
        self._vp_dirty = True

        # -- Geometría sólida --
        self.prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            uniform mat4 Mvp;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
            }
            ''',
            fragment_shader='''#version 330
            uniform vec3 color;
            out vec4 fragColor;
            void main() {
                fragColor = vec4(color, 1.0);
            }
            '''
        )

        # -- Cielo con gradiente vertical --
        self.sky_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec2 in_texcoord_0;
            uniform mat4 Mvp;
            out vec2 uv;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                uv = in_texcoord_0;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            uniform float time;
            out vec4 fragColor;
            void main() {
                vec3 top    = vec3(0.01, 0.01, 0.07);
                vec3 mid    = vec3(0.10, 0.02, 0.20);
                vec3 bottom = vec3(0.28, 0.03, 0.14);
                vec3 c = uv.y > 0.5
                    ? mix(mid,    top,    (uv.y - 0.5) * 2.0)
                    : mix(bottom, mid,    uv.y * 2.0);
                float horizon_glow = smoothstep(0.55, 0.45, uv.y) * smoothstep(0.35, 0.45, uv.y);
                float pulse = 0.85 + 0.15 * sin(time * 0.6);
                c += vec3(0.18, 0.0, 0.22) * horizon_glow * pulse * 0.6;
                fragColor = vec4(c, 1.0);
            }
            '''
        )

        # -- Rejilla synthwave en el suelo --
        self.grid_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec2 in_texcoord_0;
            uniform mat4 Mvp;
            out vec2 uv;
            out vec3 world_pos;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                uv        = in_texcoord_0;
                world_pos = in_position;
            }
            ''',
            fragment_shader='''#version 330
            in vec2  uv;
            in vec3  world_pos;
            uniform float time;
            uniform float speed_offset;
            out vec4 fragColor;
            void main() {
                float z_norm = clamp((-world_pos.z) / 700.0, 0.0, 1.0);
                float fade   = smoothstep(0.0, 0.06, z_norm) * smoothstep(1.0, 0.35, z_norm);
                float line_z = fract((world_pos.z + speed_offset) / 12.0);
                float line_x = fract(world_pos.x / 3.2 + 0.5);
                float grid_z = smoothstep(0.045, 0.005, line_z) + smoothstep(0.955, 0.995, line_z);
                float grid_x = smoothstep(0.045, 0.005, line_x) + smoothstep(0.955, 0.995, line_x);
                float grid   = clamp(grid_z + grid_x * 0.6, 0.0, 1.0);
                vec3 color_a = vec3(0.85, 0.0,  0.65);
                vec3 color_b = vec3(0.0,  0.9,  1.0);
                vec3 color   = mix(color_a, color_b, z_norm);
                float pulse  = 0.82 + 0.18 * sin(time * 1.8 + z_norm * 3.0);
                fragColor = vec4(color * pulse, grid * fade * 0.75);
            }
            '''
        )

        # -- Fixtures (ventanas con parpadeo) --
        self.fixture_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec2 in_texcoord_0;
            uniform mat4 Mvp;
            out vec2 uv;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                uv = in_texcoord_0;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            uniform int   type;
            uniform float brightness;
            out vec4 fragColor;
            void main() {
                vec3 frame_color = vec3(0.15, 0.15, 0.18);
                vec3 frame_dark  = vec3(0.08, 0.08, 0.10);
                vec3 glass_light = vec3(0.68, 0.88, 0.95);
                vec3 glass_blue  = vec3(0.35, 0.68, 0.88);
                if (type == 0) {
                    if (uv.x < 0.04 || uv.x > 0.96 || uv.y < 0.04 || uv.y > 0.96)
                        { fragColor = vec4(frame_dark, 1.0); return; }
                    if (uv.x < 0.12 || uv.x > 0.88 || uv.y < 0.12 || uv.y > 0.88)
                        { fragColor = vec4(frame_color, 1.0); return; }
                    if ((uv.x > 0.46 && uv.x < 0.54) || (uv.y > 0.46 && uv.y < 0.54))
                        { fragColor = vec4(frame_color, 1.0); return; }
                    vec2 local_uv = fract(uv * 2.0);
                    float shine = smoothstep(0.2, 0.7, local_uv.x + local_uv.y);
                    vec3 glass = mix(glass_blue, glass_light, shine * 0.7);
                    fragColor = vec4(glass * brightness, 1.0);
                } else if (type == 1) {
                    if (uv.x < 0.06 || uv.x > 0.94 || uv.y < 0.03 || uv.y > 0.97)
                        { fragColor = vec4(frame_dark, 1.0); return; }
                    fragColor = vec4(frame_color, 1.0);
                }
            }
            ''',
        )

        # -- Haces de luz --
        self.light_beam_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec2 in_texcoord_0;
            uniform mat4 Mvp;
            out vec2 uv;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                uv = in_texcoord_0;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            uniform vec3  beam_color;
            uniform float intensity;
            out vec4 fragColor;
            void main() {
                float fade_v = smoothstep(0.0, 0.15, uv.y) * smoothstep(1.0, 0.25, uv.y);
                float fade_h = smoothstep(0.0, 0.45, uv.x) * smoothstep(1.0, 0.55, uv.x);
                fragColor = vec4(beam_color, fade_v * fade_h * intensity);
            }
            '''
        )

        # -- Reflexiones en suelo --
        self.reflection_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec2 in_texcoord_0;
            uniform mat4 Mvp;
            out vec2 uv;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                uv = in_texcoord_0 * 2.0 - 1.0;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            uniform vec3  reflect_color;
            uniform float intensity;
            out vec4 fragColor;
            void main() {
                float dist = length(uv);
                if (dist > 1.0) discard;
                float fade = smoothstep(1.0, 0.0, dist);
                fragColor = vec4(reflect_color, fade * intensity);
            }
            '''
        )

        # -- Neon en edificios --
        self.neon_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec2 in_texcoord_0;
            uniform mat4 Mvp;
            out vec2 uv;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                uv = in_texcoord_0 * 2.0 - 1.0;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            uniform vec3  neon_color;
            uniform float intensity;
            out vec4 fragColor;
            void main() {
                float dist  = abs(uv.y);
                float glow  = exp(-dist * 4.0) * intensity;
                float core  = smoothstep(0.18, 0.0, dist) * intensity * 1.5;
                fragColor = vec4(neon_color, clamp(glow + core, 0.0, 1.0));
            }
            '''
        )

        # -- Luna 3D --
        self.moon_prog_3d = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec3 in_normal;
            uniform mat4 Mvp;
            uniform mat4 Model;
            out vec3 v_normal;
            out vec3 v_pos;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                v_normal = mat3(Model) * in_normal;
                v_pos    = vec3(Model * vec4(in_position, 1.0));
            }
            ''',
            fragment_shader='''#version 330
            in vec3 v_normal;
            in vec3 v_pos;
            out vec4 fragColor;
            void main() {
                vec3 base_color = vec3(0.96, 0.93, 0.78);
                vec3 dark_color = vec3(0.55, 0.52, 0.40);
                vec3 light_dir  = normalize(vec3(-0.4, 0.7, 0.5));
                vec3 norm  = normalize(v_normal);
                float diff = max(dot(norm, light_dir), 0.0);
                float fill = max(dot(norm, normalize(vec3(0.5, 0.2, -0.3))), 0.0) * 0.15;
                float crater = sin(norm.x * 18.0) * sin(norm.y * 14.0) * sin(norm.z * 16.0);
                crater = smoothstep(0.3, 0.6, crater) * 0.18;
                vec3 color = mix(dark_color, base_color, diff + fill);
                color -= crater;
                float rim = pow(1.0 - diff, 3.0) * 0.3;
                color -= rim;
                fragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
            }
            '''
        )

        # -- Ruedas --
        self.wheel_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec3 in_normal;
            uniform mat4 Mvp;
            out vec3 v_normal;
            out vec3 v_pos;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                v_normal = in_normal;
                v_pos    = in_position;
            }
            ''',
            fragment_shader='''#version 330
            in vec3 v_normal;
            in vec3 v_pos;
            uniform float wheel_rotation;
            out vec4 fragColor;
            void main() {
                vec3 tire_color = vec3(0.06, 0.06, 0.07);
                vec3 rim_outer  = vec3(0.20, 0.20, 0.25);
                vec3 rim_inner  = vec3(0.10, 0.10, 0.13);
                if (abs(v_normal.x) > 0.5) {
                    float r     = length(vec2(v_pos.y, v_pos.z));
                    float max_r = 0.675;
                    if (r > max_r * 0.58) {
                        fragColor = vec4(tire_color, 1.0);
                    } else if (r > max_r * 0.505) {
                        fragColor = vec4(rim_outer, 1.0);
                    } else {
                        float angle  = atan(v_pos.y, v_pos.z) + wheel_rotation;
                        float spokes = step(0.6, sin(angle * 8.0));
                        fragColor = vec4(mix(rim_inner, rim_outer, spokes * 0.5), 1.0);
                    }
                } else {
                    fragColor = vec4(tire_color, 1.0);
                }
            }
            '''
        )

        # -- Sombras --
        self.shadow_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            uniform mat4 Mvp;
            out vec3 v_pos_out;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                v_pos_out = in_position;
            }
            ''',
            fragment_shader='''#version 330
            in vec3 v_pos_out;
            uniform float base_z;
            out vec4 fragColor;
            void main() {
                float dist_fade = smoothstep(50.0, 0.0, abs(v_pos_out.z - base_z));
                fragColor = vec4(0.01, 0.01, 0.03, 0.60 * dist_fade);
            }
            '''
        )

        # -- Estrellas --
        self.star_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec3 in_position;
            in vec2 in_texcoord_0;
            uniform mat4 Mvp;
            out vec2 uv;
            void main() {
                gl_Position = Mvp * vec4(in_position, 1.0);
                uv = in_texcoord_0 * 2.0 - 1.0;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            uniform vec3  star_color;
            uniform float brightness;
            out vec4 fragColor;
            void main() {
                float dist = length(uv);
                if (dist > 1.0) discard;
                float glow = exp(-dist * 2.2) * brightness;
                float core = smoothstep(0.30, 0.0, dist) * brightness * 1.8;
                fragColor  = vec4(star_color * (glow + core), glow + core);
            }
            '''
        )

        # -- Lluvia instanciada --
        self.rain_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec2 in_position;     // quad local [-0.5..0.5]
            in vec2 in_texcoord_0;
            // instancia
            in vec3 i_pos;           // world xyz
            in float i_alpha;
            in float i_len;
            uniform mat4 VP;         // View-Projection sin model
            out vec2 uv;
            out float v_alpha;
            void main() {
                vec3 world = i_pos + vec3(in_position.x * 0.04, in_position.y * i_len, 0.0);
                gl_Position = VP * vec4(world, 1.0);
                uv = in_texcoord_0;
                v_alpha = i_alpha;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            in float v_alpha;
            out vec4 fragColor;
            void main() {
                float fade = smoothstep(0.0, 0.2, uv.y) * smoothstep(1.0, 0.6, uv.y);
                float thin = smoothstep(0.5, 0.45, abs(uv.x - 0.5));
                fragColor  = vec4(0.55, 0.75, 1.0, thin * fade * v_alpha);
            }
            '''
        )

        # -- HUD --
        self.hud_prog = self.ctx.program(
            vertex_shader='''#version 330
            in vec2 in_position;
            in vec2 in_texcoord_0;
            out vec2 uv;
            void main() {
                gl_Position = vec4(in_position, 0.0, 1.0);
                uv = in_texcoord_0;
            }
            ''',
            fragment_shader='''#version 330
            in vec2 uv;
            uniform sampler2D hud_tex;
            out vec4 fragColor;
            void main() {
                fragColor = texture(hud_tex, uv);
            }
            '''
        )

        # MESHES
        self.cube      = geometry.cube(size=(1, 1, 1))
        self.plane     = geometry.quad_2d(size=(1, 1))
        self.wheel_vao = self._build_cylinder_vao(radius=0.675, half_width=0.28, segments=36)
        self.moon_vao  = self._build_sphere_vao(radius=1.0, stacks=32, slices=32)

        # ESTADO DE CÁMARA
        self.camera_pos = glm.vec3(0, 4.2, 11.5)
        self.PINK  = (1.0, 0.0, 0.7)
        self.CYAN  = (0.0, 1.0, 1.0)
        self.WHITE = (1.0, 1.0, 1.0)

        # ESTRELLAS
        random.seed(42)
        self.stars = []
        star_colors = [
            (1.0, 1.0, 1.0),
            (0.85, 0.90, 1.0),
            (1.0, 0.90, 0.75),
            (0.75, 0.80, 1.0),
            (1.0, 0.75, 0.90),
        ]
        for _ in range(350):
            self.stars.append({
                "x": random.uniform(-280, 280),
                "y": random.uniform(30, 160),
                "z": random.uniform(-900, -50),
                "size": random.uniform(1.2, 4.5),
                "color": random.choice(star_colors),
                "brightness": random.uniform(0.85, 1.6),
                "twinkle_phase": random.uniform(0, math.pi * 2),
                "twinkle_speed": random.uniform(0.8, 2.5),
            })

        # LLUVIA — datos para instanced rendering
        self.rain_drops = []
        rain_inst = []
        for _ in range(600):
            drop = {
                "x":     random.uniform(-30, 30),
                "y":     random.uniform(-2, 80),
                "z":     random.uniform(-200, 10),
                "speed": random.uniform(28, 55),
                "len":   random.uniform(0.4, 1.2),
                "alpha": random.uniform(0.15, 0.45),
            }
            self.rain_drops.append(drop)
            rain_inst.extend([drop["x"], drop["y"], drop["z"], drop["alpha"], drop["len"]])

        # Quad base para la gota
        quad_verts = np.array([
            -0.5, -0.5,  0.0, 0.0,
             0.5, -0.5,  1.0, 0.0,
            -0.5,  0.5,  0.0, 1.0,
             0.5, -0.5,  1.0, 0.0,
             0.5,  0.5,  1.0, 1.0,
            -0.5,  0.5,  0.0, 1.0,
        ], dtype='f4')
        self._rain_quad_vbo = self.ctx.buffer(quad_verts.tobytes())
        self._rain_inst_data = np.array(rain_inst, dtype='f4')
        self._rain_inst_vbo  = self.ctx.buffer(self._rain_inst_data.tobytes(), dynamic=True)
        self._rain_vao = self.ctx.vertex_array(self.rain_prog, [
            (self._rain_quad_vbo, '2f 2f',     'in_position', 'in_texcoord_0'),
            (self._rain_inst_vbo, '3f 1f 1f/i','i_pos', 'i_alpha', 'i_len'),
        ])

        random.seed()

        # EDIFICIOS
        self.buildings = []
        sides = [(-22, -30), (22, 30)]
        for base_x, offset_x in sides:
            for i in range(160):
                w = random.random() * 4 + 6.0
                h = random.random() * 35 + 18.0
                d = random.random() * 4 + 5.0
                fixtures = [{"rel_x": 0.0, "rel_y": 1.5, "sw": 1.6, "sh": 2.8, "type": 1}]

                win_w, win_h   = 1.3, 1.3
                padding_x, padding_y = 0.6, 1.4
                cols = max(1, int((w - 1.0) / (win_w + padding_x)))
                rows = max(1, int((h - 4.5) / (win_h + padding_y)))
                total_grid_w = (cols * win_w) + ((cols - 1) * padding_x)
                start_x = -total_grid_w / 2.0 + (win_w / 2.0)

                for r in range(rows):
                    y_pos = 4.8 + r * (win_h + padding_y)
                    if y_pos + (win_h / 2.0) > h - 1.0:
                        break
                    for c in range(cols):
                        win_seed = (i * 1000 + r * 100 + c) % 10000
                        if random.random() > 0.25:
                            fixtures.append({
                                "rel_x":    start_x + c * (win_w + padding_x),
                                "rel_y":    y_pos,
                                "sw":       win_w,
                                "sh":       win_h,
                                "type":     0,
                                "win_seed": win_seed,
                            })

                r_tone = random.uniform(0.05, 0.15)
                g_tone = random.uniform(0.04, 0.10)
                b_tone = random.uniform(0.22, 0.35)

                self.buildings.append({
                    "x": base_x + (random.random() * offset_x),
                    "z": -i * 12,
                    "w": w, "h": h, "d": d,
                    "color": (r_tone, g_tone, b_tone),
                    "fixtures": fixtures,
                })

        self.hud_tex = self._build_hud()
        # VAO/VBO del HUD reutilizable (se actualiza con write si la ventana cambia)
        self._hud_vbo = None
        self._hud_vao = None
        self._last_win_size = None

    # HUD — creado una sola vez, reutilizado cada frame
    def _build_hud(self):
        from PIL import Image, ImageDraw, ImageFont

        W, H = 260, 180
        img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=10,
                               fill=(8, 4, 20, 195), outline=(180, 0, 255, 220), width=2)

        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
            font_key   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            font_desc  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            font_speed = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        except Exception:
            font_title = font_key = font_desc = font_speed = ImageFont.load_default()

        draw.text((W // 2, 12), "CONTROLES DE CÁMARA", font=font_title,
                  fill=(200, 0, 255, 255), anchor="mm")
        draw.line([(12, 24), (W - 12, 24)], fill=(180, 0, 255, 160), width=1)

        controls = [
            ("A", "Rotar izquierda"),
            ("D", "Rotar derecha"),
            ("W", "Zoom acercar"),
            ("S", "Zoom alejar"),
            ("Q", "Subir cámara"),
            ("E", "Bajar cámara"),
        ]
        cy = 34
        for key, desc in controls:
            draw.rounded_rectangle([12, cy, 30, cy + 16], radius=3,
                                   fill=(180, 0, 255, 180), outline=(255, 100, 255, 200), width=1)
            draw.text((21, cy + 8), key,  font=font_key,  fill=(255, 255, 255, 255), anchor="mm")
            draw.text((38, cy + 8), desc, font=font_desc, fill=(200, 180, 255, 230), anchor="lm")
            cy += 20

        draw.line([(12, cy + 2), (W - 12, cy + 2)], fill=(180, 0, 255, 100), width=1)
        draw.text((W // 2, cy + 18), "", font=font_speed,
                  fill=(0, 255, 220, 255), anchor="mm")

        img  = img.transpose(Image.FLIP_TOP_BOTTOM)
        data = np.array(img, dtype='u1')
        tex  = self.ctx.texture((W, H), 4, data.tobytes())
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._hud_w = W
        self._hud_h = H
        return tex

    # CONSTRUCTORES DE MESH
    def _build_sphere_vao(self, radius=1.0, stacks=32, slices=32):
        verts, normals = [], []
        for i in range(stacks):
            phi0 = math.pi * i / stacks
            phi1 = math.pi * (i + 1) / stacks
            for j in range(slices):
                theta0 = 2 * math.pi * j / slices
                theta1 = 2 * math.pi * (j + 1) / slices

                def vert(phi, theta):
                    x = radius * math.sin(phi) * math.cos(theta)
                    y = radius * math.cos(phi)
                    z = radius * math.sin(phi) * math.sin(theta)
                    return [x, y, z], [x / radius, y / radius, z / radius]

                p00, n00 = vert(phi0, theta0)
                p01, n01 = vert(phi0, theta1)
                p10, n10 = vert(phi1, theta0)
                p11, n11 = vert(phi1, theta1)
                verts.extend(p00); normals.extend(n00)
                verts.extend(p10); normals.extend(n10)
                verts.extend(p11); normals.extend(n11)
                verts.extend(p00); normals.extend(n00)
                verts.extend(p11); normals.extend(n11)
                verts.extend(p01); normals.extend(n01)

        vbo_pos = self.ctx.buffer(np.array(verts,   dtype='f4').tobytes())
        vbo_nor = self.ctx.buffer(np.array(normals, dtype='f4').tobytes())
        return self.ctx.vertex_array(self.moon_prog_3d, [
            (vbo_pos, '3f', 'in_position'),
            (vbo_nor, '3f', 'in_normal'),
        ])

    def _build_cylinder_vao(self, radius, half_width, segments):
        verts, normals = [], []

        def add_tri(p0, n0, p1, n1, p2, n2):
            verts.extend(p0); normals.extend(n0)
            verts.extend(p1); normals.extend(n1)
            verts.extend(p2); normals.extend(n2)

        for i in range(segments):
            a0 = 2 * math.pi * i / segments
            a1 = 2 * math.pi * (i + 1) / segments
            y0, z0 = radius * math.sin(a0), radius * math.cos(a0)
            y1, z1 = radius * math.sin(a1), radius * math.cos(a1)
            s0 = [0, math.sin(a0), math.cos(a0)]
            s1 = [0, math.sin(a1), math.cos(a1)]
            add_tri([-half_width, y0, z0], s0, [ half_width, y0, z0], s0, [ half_width, y1, z1], s1)
            add_tri([-half_width, y0, z0], s0, [ half_width, y1, z1], s1, [-half_width, y1, z1], s1)
            add_tri([-half_width, 0, 0], [-1,0,0], [-half_width, y1, z1], [-1,0,0], [-half_width, y0, z0], [-1,0,0])
            add_tri([ half_width, 0, 0], [1, 0,0], [ half_width, y0, z0], [1, 0,0],  [ half_width, y1, z1], [1, 0,0])

        vbo_pos = self.ctx.buffer(np.array(verts,   dtype='f4').tobytes())
        vbo_nor = self.ctx.buffer(np.array(normals, dtype='f4').tobytes())
        return self.ctx.vertex_array(self.wheel_prog, [
            (vbo_pos, '3f', 'in_position'),
            (vbo_nor, '3f', 'in_normal'),
        ])

    # TECLADO
    def on_key_event(self, key, action, modifiers):
        keys = self.wnd.keys
        if action == keys.ACTION_PRESS:
            self.keys_held.add(key)
        elif action == keys.ACTION_RELEASE:
            self.keys_held.discard(key)

    def key_held_update(self, frame_time):
        keys       = self.wnd.keys
        speed      = 8.0  * frame_time
        zoom_speed = 5.0  * frame_time
        rot_speed  = 1.5  * frame_time
        if keys.A in self.keys_held: self.cam_yaw    -= rot_speed
        if keys.D in self.keys_held: self.cam_yaw    += rot_speed
        if keys.W in self.keys_held: self.cam_zoom   -= zoom_speed
        if keys.S in self.keys_held: self.cam_zoom   += zoom_speed
        if keys.Q in self.keys_held: self.cam_height += speed
        if keys.E in self.keys_held: self.cam_height -= speed

    # CÁMARA
    def get_camera(self):
        base_pos    = glm.vec3(0, 4.2, 11.5)
        target_base = glm.vec3(0, 3, -200)
        cam_pos     = glm.vec3(base_pos.x, base_pos.y + self.cam_height, base_pos.z + self.cam_zoom)
        yaw_rot         = glm.rotate(glm.mat4(1.0), self.cam_yaw, glm.vec3(0, 1, 0))
        cam_pos_rotated = glm.vec3(yaw_rot * glm.vec4(cam_pos,     1.0))
        target_rotated  = glm.vec3(yaw_rot * glm.vec4(target_base, 1.0))
        return cam_pos_rotated, target_rotated

    def _compute_vp(self):
        """View-Projection cacheado para el frame actual."""
        if self._vp_cache is None:
            cam_pos, cam_target = self.get_camera()
            projection = glm.perspective(glm.radians(75.0), self.wnd.aspect_ratio, 0.1, 2000.0)
            view       = glm.lookAt(cam_pos, cam_target, glm.vec3(0, 1, 0))
            self._vp_cache = projection * view
        return self._vp_cache

    def get_mvp(self, model):
        return self._compute_vp() * model

    # HELPERS DE DIBUJO
    def cube_draw(self, x, y, z, sx, sy, sz, color):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, y, z))
        model = glm.scale(model, glm.vec3(sx, sy, sz))
        self.prog['Mvp'].write(self.get_mvp(model))
        self.prog['color'].value = color
        self.cube.render(self.prog)

    def shadow_draw(self, x, y, z, sx, sy, sz, skew_x, skew_z, origin_z=0.0):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, -0.88, z))
        shear        = glm.mat4(1.0)
        shear[1][0]  = skew_x
        shear[1][2]  = skew_z
        model = model * shear
        model = glm.scale(model, glm.vec3(sx, sy, sz))
        self.shadow_prog['Mvp'].write(self.get_mvp(model))
        self.shadow_prog['base_z'].value = origin_z
        self.cube.render(self.shadow_prog)

    def fixture_draw(self, x, y, z, sx, sy, fixture_type, brightness=1.0):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, y, z))
        model = glm.scale(model, glm.vec3(sx, sy, 1.0))
        self.fixture_prog['Mvp'].write(self.get_mvp(model))
        self.fixture_prog['type'].value       = fixture_type
        self.fixture_prog['brightness'].value = brightness
        self.plane.render(self.fixture_prog)

    def draw_light_beam(self, x, y, z, rx, ry, rz, sx, sy, color, intensity=0.4):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, y, z))
        model = glm.rotate(model, glm.radians(rx), glm.vec3(1, 0, 0))
        model = glm.rotate(model, glm.radians(ry), glm.vec3(0, 1, 0))
        model = glm.rotate(model, glm.radians(rz), glm.vec3(0, 0, 1))
        model = glm.scale(model, glm.vec3(sx, sy, 1.0))
        self.light_beam_prog['Mvp'].write(self.get_mvp(model))
        self.light_beam_prog['beam_color'].value = color
        self.light_beam_prog['intensity'].value  = intensity
        self.plane.render(self.light_beam_prog)

    def draw_street_reflection(self, x, z, size_x, size_z, color, intensity=0.3):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, -0.94, z))
        model = glm.rotate(model, glm.radians(90.0), glm.vec3(1, 0, 0))
        model = glm.scale(model, glm.vec3(size_x, size_z, 1.0))
        self.reflection_prog['Mvp'].write(self.get_mvp(model))
        self.reflection_prog['reflect_color'].value = color
        self.reflection_prog['intensity'].value     = intensity
        self.plane.render(self.reflection_prog)

    def draw_round_wheel(self, x, y, z, diameter_size, depth_width, rotation=0.0):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, y, z))
        model = glm.scale(model, glm.vec3(diameter_size, diameter_size, diameter_size))
        self.wheel_prog['Mvp'].write(self.get_mvp(model))
        self.wheel_prog['wheel_rotation'].value = rotation
        self.wheel_vao.render()

    def draw_moon_3d(self, x, y, z, size):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, y, z))
        model = glm.scale(model, glm.vec3(size, size, size))
        self.moon_prog_3d['Mvp'].write(self.get_mvp(model))
        self.moon_prog_3d['Model'].write(model)
        self.moon_vao.render()

    def draw_star(self, x, y, z, size, color, brightness):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, y, z))
        model = glm.scale(model, glm.vec3(size, size, 1.0))
        self.star_prog['Mvp'].write(self.get_mvp(model))
        self.star_prog['star_color'].value = color
        self.star_prog['brightness'].value = brightness
        self.plane.render(self.star_prog)

    def draw_sky_quad(self, time):
        model = glm.translate(glm.mat4(1.0), glm.vec3(0, 70, -600))
        model = glm.scale(model, glm.vec3(1400, 280, 1.0))
        self.sky_prog['Mvp'].write(self.get_mvp(model))
        self.sky_prog['time'].value = time
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.plane.render(self.sky_prog)
        self.ctx.enable(moderngl.DEPTH_TEST)

    def draw_synthwave_grid(self, time, speed_factor):
        model = glm.translate(glm.mat4(1.0), glm.vec3(0, -0.92, -350))
        model = glm.rotate(model, glm.radians(90.0), glm.vec3(1, 0, 0))
        model = glm.scale(model, glm.vec3(16.0, 700.0, 1.0))
        self.grid_prog['Mvp'].write(self.get_mvp(model))
        self.grid_prog['time'].value         = time
        self.grid_prog['speed_offset'].value = time * speed_factor % 12.0
        self.plane.render(self.grid_prog)

    def draw_neon_strip(self, x, y, z, width, neon_color, intensity):
        model = glm.translate(glm.mat4(1.0), glm.vec3(x, y, z))
        model = glm.scale(model, glm.vec3(width, 0.30, 1.0))
        self.neon_prog['Mvp'].write(self.get_mvp(model))
        self.neon_prog['neon_color'].value = neon_color
        self.neon_prog['intensity'].value  = intensity
        self.plane.render(self.neon_prog)

    def draw_hud(self):
        win_size = self.wnd.size
        win_w, win_h = win_size

        # Reconstruir VAO/VBO solo si la ventana cambió de tamaño
        if self._last_win_size != win_size:
            pad = 14
            x0 = -1.0 + (pad / win_w) * 2
            y0 = -1.0 + (pad / win_h) * 2
            x1 = x0 + (self._hud_w / win_w) * 2
            y1 = y0 + (self._hud_h / win_h) * 2

            verts = np.array([
                x0, y0, 0.0, 0.0,
                x1, y0, 1.0, 0.0,
                x0, y1, 0.0, 1.0,
                x1, y0, 1.0, 0.0,
                x1, y1, 1.0, 1.0,
                x0, y1, 0.0, 1.0,
            ], dtype='f4')

            if self._hud_vbo is not None:
                self._hud_vbo.release()
                self._hud_vao.release()

            self._hud_vbo = self.ctx.buffer(verts.tobytes())
            self._hud_vao = self.ctx.vertex_array(
                self.hud_prog,
                [(self._hud_vbo, '2f 2f', 'in_position', 'in_texcoord_0')]
            )
            self._last_win_size = win_size

        self.hud_tex.use(0)
        self.hud_prog['hud_tex'].value = 0
        self.ctx.disable(moderngl.DEPTH_TEST)
        self._hud_vao.render(moderngl.TRIANGLES)
        self.ctx.enable(moderngl.DEPTH_TEST)

    # RENDER PRINCIPAL
    def on_render(self, time, frame_time):
        self.key_held_update(frame_time)
        # Invalidar caché VP al comienzo de cada frame
        self._vp_cache = None

        self.ctx.clear(0.01, 0.01, 0.04)

        speed_factor = 20.0
        bounce = math.sin(time * 0.6) * 0.006

        # ── 1. Cielo ──────────────────────────────────────
        self.draw_sky_quad(time)

        # ── 2. Estrellas (blending ONE) ───────────────────
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)

        for star in self.stars:
            twinkle = 0.85 + 0.15 * math.sin(time * star["twinkle_speed"] + star["twinkle_phase"])
            self.draw_star(star["x"], star["y"], star["z"],
                           star["size"], star["color"],
                           star["brightness"] * twinkle)

        # ── 3. Luna + halo ────────────────────────────────
        moon_pulse = 0.82 + 0.18 * math.sin(time * 1.1)
        moon_pulse2 = 0.88 + 0.12 * math.sin(time * 1.7 + 1.2)

        # Halo exterior muy difuso
        self.draw_star(0.0, 158.0, -449.5, 500.0, (0.80, 0.65, 0.40), 0.08 * moon_pulse)
        # Halo exterior medio
        self.draw_star(0.0, 158.0, -449.5, 340.0, (0.90, 0.78, 0.55), 0.15 * moon_pulse)
        # Halo medio brillante
        self.draw_star(0.0, 158.0, -449.5, 220.0, (0.98, 0.92, 0.70), 0.30 * moon_pulse2)
        # Halo interno intenso
        self.draw_star(0.0, 158.0, -449.5, 120.0, (1.00, 0.97, 0.85), 0.65 * moon_pulse2)
        # Corona muy cercana
        self.draw_star(0.0, 158.0, -449.5,  70.0, (1.00, 1.00, 0.95), 0.90)

        # Resplandor radial fijo — 32 rayos en círculo completo
        ray_color = (1.00, 0.97, 0.82)
        num_rays  = 32
        for i in range(num_rays):
            ang_deg = (360.0 / num_rays) * i
            ang_rad = math.radians(ang_deg)
            ray_len   = 80.0
            ray_alpha = 0.15
            ray_w     = 9.0
            ox = math.cos(ang_rad) * ray_len * 0.5
            oy = math.sin(ang_rad) * ray_len * 0.5
            self.draw_light_beam(ox, 158.0 + oy, -449.3,
                                 0.0, 0.0, ang_deg, ray_w, ray_len,
                                 ray_color, ray_alpha)

        self.ctx.disable(moderngl.BLEND)
        self.draw_moon_3d(0.0, 158.0, -450.0, 45.0)

        # ── 5. Suelo ──────────────────────────────────────
        SIDEWALK_COLOR  = (0.22, 0.21, 0.28)
        CURB_COLOR      = (0.30, 0.28, 0.36)
        CURB_EDGE_COLOR = (0.14, 0.13, 0.18)

        self.cube_draw(0, -1, -800, 18, 0.02, 2000, (0.16, 0.16, 0.20))

        for side in [-1, 1]:
            sx = side * 13.5
            self.cube_draw(sx, -0.80, -800, 9.0, 0.02, 2000, SIDEWALK_COLOR)
            self.cube_draw(side * 9.1,  -0.72, -800, 0.35, 0.18, 2000, CURB_COLOR)
            self.cube_draw(side * 17.9, -0.82, -800, 0.35, 0.12, 2000, CURB_EDGE_COLOR)
            for i in range(200):
                z = -(i * 8) + (time * speed_factor % 8)
                self.cube_draw(sx, -0.79, z, 9.0, 0.025, 0.08, (0.12, 0.11, 0.16))

        self.cube_draw(-8, -0.95, -800, 0.15, 0.02, 2000, self.WHITE)
        self.cube_draw( 8, -0.95, -800, 0.15, 0.02, 2000, self.WHITE)
        for i in range(200):
            z = -(i * 12) + (time * speed_factor % 12)
            self.cube_draw(0, -0.9, z, 0.15, 0.02, 3, self.WHITE)

        # ── 6. Rejilla synthwave ──────────────────────────
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        self.draw_synthwave_grid(time, speed_factor)

        # ── 7. Edificios + ventanas ───────────────────────
        # Culling: solo edificios dentro del rango visible
        VIEW_NEAR = -5
        VIEW_FAR  = -800
        self.ctx.disable(moderngl.BLEND)

        for b in self.buildings:
            z_animated = b["z"] + (time * speed_factor % 1920)
            if z_animated > 40:
                z_animated -= 1920

            # Skip edificios fuera del frustum Z
            if z_animated < VIEW_FAR or z_animated > VIEW_NEAR:
                continue

            self.cube_draw(b["x"], b["h"] / 2, z_animated, b["w"], b["h"], b["d"], b["color"])

            for f in b["fixtures"]:
                brightness = 1.0
                if f.get("type") == 0:
                    ws    = f.get("win_seed", 0)
                    flick = math.sin(time * 1.8 + ws * 0.37) * 0.15 + \
                            math.sin(time * 3.1 + ws * 0.91) * 0.06
                    brightness = max(0.35, 0.88 + flick)
                    if math.sin(time * 0.4 + ws * 1.7) > 0.92:
                        brightness = 0.05

                self.fixture_draw(
                    b["x"] + f["rel_x"], f["rel_y"],
                    z_animated + b["d"] / 2 + 0.01,
                    f["sw"], f["sh"], f["type"],
                    brightness=brightness
                )

        # ── 8. Sombras (blend normal) ─────────────────────
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        for i in range(80):
            z = -(i * 20) + (time * speed_factor % 20)
            for side in [-10, 10]:
                self.shadow_draw(side, 3.0, z, 0.08, 6.0, 0.08, -1.4, 1.2, origin_z=z)
        self.shadow_draw(0.0, 0.5, 0.0, 4.4, 0.4, 7.4, 0.0, 0.4, origin_z=0.0)
        self.ctx.disable(moderngl.BLEND)

        # ── 9. Postes de luz ──────────────────────────────
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        for i in range(80):
            z = -(i * 20) + (time * speed_factor % 20)
            for side in [-10, 10]:
                self.ctx.disable(moderngl.BLEND)
                self.cube_draw(side, 4, z, 0.08, 8, 0.08, (0.05, 0.05, 0.08))
                self.cube_draw(side, 8, z, 0.5, 0.15, 0.5, (1.0, 1.0, 0.7))
                self.ctx.enable(moderngl.BLEND)
                self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
                ref_offset_x = side * 0.75
                self.draw_street_reflection(ref_offset_x, z, 9.0, 6.0,
                                            (1.0, 0.88, 0.45), intensity=0.55)

        # ── 10. Carrocería del coche ──────────────────────
        self.ctx.disable(moderngl.BLEND)

        CAR_BASE  = (0.75, 0.0, 0.35)
        CAR_MID   = (0.85, 0.0, 0.42)
        CAR_DARK  = (0.55, 0.0, 0.25)

        self.cube_draw(0, 0.38 + bounce, 0,    4.2, 0.55, 7.2, CAR_BASE)
        self.cube_draw(0, 0.75 + bounce, -2.5, 4.0, 0.18, 2.2, CAR_BASE)
        self.cube_draw(0, 0.90 + bounce, -2.5, 1.2, 0.22, 1.8, (0.80, 0.0, 0.38))
        self.cube_draw(0, 1.08 + bounce, -0.3, 2.6, 0.62, 3.0, CAR_MID)

        self.cube_draw(0,     0.95 + bounce,  1.3,  2.4, 0.38, 0.02, self.CYAN)
        self.cube_draw(0,     1.08 + bounce,  0.82, 2.2, 0.40, 0.02, self.CYAN)
        self.cube_draw(0,     1.08 + bounce, -1.82, 2.0, 0.40, 0.02, self.CYAN)
        self.cube_draw(-1.30, 1.08 + bounce, -0.5,  0.02, 0.40, 3.0, self.CYAN)
        self.cube_draw( 1.30, 1.08 + bounce, -0.5,  0.02, 0.40, 3.0, self.CYAN)

        self.cube_draw(-2.25, 0.10 + bounce, -0.2, 0.18, 0.22, 5.8, CAR_DARK)
        self.cube_draw( 2.25, 0.10 + bounce, -0.2, 0.18, 0.22, 5.8, CAR_DARK)

        self.cube_draw(0,    0.18 + bounce, -3.70, 4.0,  0.35, 0.30, (0.60, 0.0, 0.28))
        self.cube_draw(0,    0.42 + bounce, -3.62, 3.8,  0.28, 0.20, (0.70, 0.0, 0.32))
        self.cube_draw(-1.4, 0.28 + bounce, -3.68, 0.85, 0.28, 0.12, (0.08, 0.08, 0.10))
        self.cube_draw( 1.4, 0.28 + bounce, -3.68, 0.85, 0.28, 0.12, (0.08, 0.08, 0.10))
        self.cube_draw(0,    0.38 + bounce, -3.64, 1.8,  0.26, 0.12, (0.08, 0.05, 0.12))

        self.cube_draw(0,    0.18 + bounce,  3.72, 4.0,  0.30, 0.30, (0.60, 0.0, 0.28))
        self.cube_draw(-1.0, 0.08 + bounce,  3.78, 0.80, 0.18, 0.20, (0.08, 0.05, 0.12))
        self.cube_draw( 1.0, 0.08 + bounce,  3.78, 0.80, 0.18, 0.20, (0.08, 0.05, 0.12))
        self.cube_draw(-1.0, 0.07 + bounce,  3.82, 0.35, 0.12, 0.06, (0.65, 0.62, 0.68))
        self.cube_draw( 1.0, 0.07 + bounce,  3.82, 0.35, 0.12, 0.06, (0.65, 0.62, 0.68))

        self.cube_draw(0,    1.15 + bounce, 3.30, 3.6,  0.10, 0.30, (0.90, 0.0, 0.45))
        self.cube_draw(-1.6, 0.90 + bounce, 3.20, 0.12, 0.55, 0.28, (0.70, 0.0, 0.35))
        self.cube_draw( 1.6, 0.90 + bounce, 3.20, 0.12, 0.55, 0.28, (0.70, 0.0, 0.35))

        self.cube_draw(-2.18, 0.88 + bounce, -1.6, 0.22, 0.12, 0.35, (0.15, 0.15, 0.15))
        self.cube_draw( 2.18, 0.88 + bounce, -1.6, 0.22, 0.12, 0.35, (0.15, 0.15, 0.15))

        self.cube_draw(-1.35, 0.52 + bounce, -3.72, 0.85, 0.14, 0.05, (1.0, 0.95, 0.65))
        self.cube_draw( 1.35, 0.52 + bounce, -3.72, 0.85, 0.14, 0.05, (1.0, 0.95, 0.65))
        self.cube_draw(-1.35, 0.62 + bounce, -3.70, 0.90, 0.05, 0.04, (1.0, 1.0, 0.85))
        self.cube_draw( 1.35, 0.62 + bounce, -3.70, 0.90, 0.05, 0.04, (1.0, 1.0, 0.85))

        self.cube_draw(-1.35, 0.72 + bounce, 3.62, 1.1, 0.10, 0.05, (1.0, 0.0, 0.15))
        self.cube_draw( 1.35, 0.72 + bounce, 3.62, 1.1, 0.10, 0.05, (1.0, 0.0, 0.15))

        # Neón bajo el chasis
        under_glow_pulse = 0.7 + 0.3 * math.sin(time * 1.2)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        self.draw_street_reflection(0.0, 0.0, 5.5, 8.5,
                                    (0.9, 0.0, 0.55), intensity=under_glow_pulse * 0.45)

        # ── 11. Ruedas ────────────────────────────────────
        self.ctx.disable(moderngl.BLEND)
        wheel_rot = time * 80.0 * (math.pi / 180.0)
        for wx, wz in [(-2.1, -2.4), (2.1, -2.4), (-2.1, 2.4), (2.1, 2.4)]:
            self.draw_round_wheel(wx, -0.28 + bounce, wz, 1.05, 0.60, rotation=wheel_rot)

        # ── 12. Haces de luz y reflejos ───────────────────
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)

        self.draw_light_beam(-1.35, -0.94, -18.0, 90.0, 0.0, 0.0, 6.5, 30.0,
                             (1.0, 0.92, 0.65), intensity=0.40)
        self.draw_light_beam( 1.35, -0.94, -18.0, 90.0, 0.0, 0.0, 6.5, 30.0,
                             (1.0, 0.92, 0.65), intensity=0.40)
        self.draw_light_beam(-1.1,  -0.94, 10.0 + bounce, 90.0, 0.0, 0.0, 4.5, 14.0,
                             (1.0, 0.0, 0.2), intensity=0.38)
        self.draw_light_beam( 1.1,  -0.94, 10.0 + bounce, 90.0, 0.0, 0.0, 4.5, 14.0,
                             (1.0, 0.0, 0.2), intensity=0.38)

        self.draw_street_reflection(-1.35, -15.0, 4.0, 25.0, (1.0, 0.95, 0.70), intensity=0.50)
        self.draw_street_reflection( 1.35, -15.0, 4.0, 25.0, (1.0, 0.95, 0.70), intensity=0.50)
        self.draw_street_reflection(  0.0, -10.0, 6.0, 15.0, (1.0, 0.95, 0.70), intensity=0.30)
        self.draw_street_reflection(-1.35, -22.0, 2.5, 38.0, (1.0, 0.97, 0.75), intensity=0.65)
        self.draw_street_reflection( 1.35, -22.0, 2.5, 38.0, (1.0, 0.97, 0.75), intensity=0.65)
        self.draw_street_reflection(  0.0, -18.0, 5.0, 28.0, (1.0, 0.96, 0.70), intensity=0.30)

        # ── 13. Lluvia instanciada ────────────────────────
        cam_pos, _ = self.get_camera()
        inst_data  = self._rain_inst_data.reshape(-1, 5)

        for idx, drop in enumerate(self.rain_drops):
            drop["y"] -= drop["speed"] * frame_time
            if drop["y"] < -2.0:
                drop["y"]   = random.uniform(60, 80)
                drop["x"]   = cam_pos.x + random.uniform(-30, 30)
                drop["z"]   = cam_pos.z + random.uniform(-80, 20)
                drop["alpha"] = random.uniform(0.15, 0.45)
            inst_data[idx, 0] = drop["x"]
            inst_data[idx, 1] = drop["y"]
            inst_data[idx, 2] = drop["z"]
            inst_data[idx, 3] = drop["alpha"]
            inst_data[idx, 4] = drop["len"]

        self._rain_inst_vbo.write(self._rain_inst_data.tobytes())

        # Pasar VP directamente al shader de lluvia (no usa Model)
        vp = self._compute_vp()
        self.rain_prog['VP'].write(vp)
        self._rain_vao.render(moderngl.TRIANGLES, instances=len(self.rain_drops))

        self.ctx.disable(moderngl.BLEND)

        # ── 14. HUD ───────────────────────────────────────
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        self.draw_hud()
        self.ctx.disable(moderngl.BLEND)


if __name__ == '__main__':
    mglw.run_window_config(SynthwaveDrive)