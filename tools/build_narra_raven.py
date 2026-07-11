import bpy
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "service" / "static" / "assets" / "narra-raven.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, color, metallic=0.08, roughness=0.72, emission=None, strength=0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    return material


INK = mat("Ink black", (0.018, 0.014, 0.032), roughness=0.82)
MIDNIGHT = mat("Midnight violet", (0.035, 0.022, 0.075), roughness=0.72)
PURPLE = mat("Narra purple", (0.085, 0.042, 0.17), roughness=0.64)
LILAC = mat("Facet lilac", (0.17, 0.105, 0.28), roughness=0.6)
BEAK = mat("Beak", (0.025, 0.025, 0.043), roughness=0.88)
LEG = mat("Legs", (0.12, 0.075, 0.17), roughness=0.86)
EMBER = mat("Ember iris", (1.0, 0.34, 0.015), roughness=0.3, emission=(1.0, 0.12, 0.0), strength=2.2)
PUPIL = mat("Pupil", (0.002, 0.001, 0.001), roughness=0.55)


def empty(name, location=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.location = location
    bpy.context.collection.objects.link(obj)
    if parent:
        obj.parent = parent
    return obj


def assign(obj, material):
    obj.data.materials.append(material)
    return obj


def ico(name, location, scale, material, parent=None, subdivisions=1, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    assign(obj, material)
    if parent:
        obj.parent = parent
    return obj


def cylinder(name, location, radius, depth, material, parent=None, rotation=(0, 0, 0), vertices=5):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    assign(obj, material)
    if parent:
        obj.parent = parent
    return obj


def cone(name, location, radius, depth, material, parent=None, rotation=(0, 0, 0), vertices=4):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=0, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    assign(obj, material)
    if parent:
        obj.parent = parent
    return obj


def prism(name, points, depth, material, parent=None):
    verts = [(x, -depth / 2, z) for x, z in points] + [(x, depth / 2, z) for x, z in points]
    n = len(points)
    faces = [tuple(range(n))[::-1], tuple(range(n, n * 2))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    assign(obj, material)
    if parent:
        obj.parent = parent
    return obj


def feather(name, base, tip, width, material, parent, depth=0.085, shoulder=0.55):
    base = Vector(base)
    tip = Vector(tip)
    vector = tip - base
    length = vector.length
    center = (base + tip) / 2
    points = [
        (-width * 0.34, length / 2),
        (width * 0.34, length / 2),
        (width / 2, length * 0.04),
        (width * shoulder, -length * 0.18),
        (0, -length / 2),
        (-width * shoulder, -length * 0.18),
        (-width / 2, length * 0.04),
    ]
    obj = prism(name, points, depth, material, parent)
    obj.location = (center.x, base[1], center.z)
    obj.rotation_euler[1] = math.atan2(-vector.x, vector.z)
    obj.rotation_euler[2] = 0
    return obj


root = empty("RAVEN_ROOT")
body = empty("BODY", parent=root)
head = empty("HEAD", (-0.54, 0, 1.46), root)
throat = empty("THROAT", (-0.42, 0, 0.98), root)
wing = empty("WING_FRONT", (0, -0.42, 0), root)
wing_back = empty("WING_BACK", (0.03, 0.42, 0.01), root)
tail = empty("TAIL", (0.68, 0, -0.32), root)
leg_front = empty("LEG_FRONT", (-0.02, -0.28, -1.02), root)
leg_back = empty("LEG_BACK", (0.26, 0.23, -1.0), root)

# Full, proud raven body and chest.
ico("BodyCore", (0.08, 0, 0.08), (0.82, 0.62, 1.22), INK, body, subdivisions=2, rotation=(0, 0.12, -0.08))
ico("Chest", (-0.38, -0.04, 0.28), (0.65, 0.58, 0.91), MIDNIGHT, body, subdivisions=1, rotation=(0, 0, 0.14))
ico("Rump", (0.5, 0.03, -0.04), (0.67, 0.55, 0.82), MIDNIGHT, body, subdivisions=1, rotation=(0, 0, -0.24))

# Oversized raven head, brow ridge, and broad wedge bill.
ico("Skull", (0, 0, 0), (0.69, 0.58, 0.63), MIDNIGHT, head, subdivisions=2, rotation=(0, 0, -0.04))
feather("BrowFeather", (-0.36, -0.59, 0.28), (-0.02, -0.59, 0.52), 0.44, PURPLE, head, depth=0.12)
upper = prism("UPPER_BEAK", [(-0.98, -0.08), (-0.45, 0.23), (0.0, 0.17), (0.0, -0.15), (-0.62, -0.22)], 0.48, BEAK, head)
upper.location = (-0.42, 0, 0.02)
lower_group = empty("LOWER_BEAK", (-0.4, 0, -0.05), head)
lower = prism("LowerBillMesh", [(-0.88, -0.06), (-0.22, 0.09), (0.04, 0.06), (0.04, -0.09), (-0.58, -0.17)], 0.38, BEAK, lower_group)
lower.location = (-0.22, 0, -0.08)

ico("EyeIris", (-0.31, -0.555, 0.12), (0.14, 0.055, 0.14), EMBER, head, subdivisions=2)
ico("EyePupil", (-0.33, -0.604, 0.125), (0.06, 0.025, 0.067), PUPIL, head, subdivisions=2)
ico("EyeGlint", (-0.355, -0.624, 0.175), (0.022, 0.012, 0.022), LILAC, head, subdivisions=1)
ico("EyeIrisBack", (-0.31, 0.555, 0.12), (0.14, 0.055, 0.14), EMBER, head, subdivisions=2)
ico("EyePupilBack", (-0.33, 0.604, 0.125), (0.06, 0.025, 0.067), PUPIL, head, subdivisions=2)
ico("EyeGlintBack", (-0.355, 0.624, 0.175), (0.022, 0.012, 0.022), LILAC, head, subdivisions=1)

# Layered cheek, crown, and throat hackles from reference.
head_layers = [
    ((0.18, -0.43, 0.4), (0.52, -0.43, 0.12), 0.48, PURPLE),
    ((0.32, -0.38, 0.2), (0.65, -0.38, -0.04), 0.5, MIDNIGHT),
    ((-0.02, -0.4, -0.2), (0.42, -0.4, -0.36), 0.52, LILAC),
]
for i, (base, tip, width, material) in enumerate(head_layers):
    feather(f"HeadLayer{i}", base, tip, width, material, head, depth=0.12)

for i in range(7):
    x = -0.28 + i * 0.1
    feather(f"ThroatHackle{i}", (x, -0.36 - (i % 2) * 0.025, 0.2 - i * 0.055),
            (x - 0.12 + i * 0.035, -0.36, -0.42 - i * 0.035), 0.28 + (i % 3) * 0.04,
            [MIDNIGHT, PURPLE, LILAC][i % 3], throat, depth=0.09)

# Front folded wing: shingled coverts over long overlapping flight feathers.
ico("WingMass", (0.3, 0, 0.18), (0.77, 0.25, 0.96), MIDNIGHT, wing, subdivisions=1, rotation=(0, 0.1, -0.35))
for row in range(3):
    for col in range(4):
        bx = -0.18 + col * 0.3 + row * 0.08
        bz = 0.72 - row * 0.32 - col * 0.08
        length = 0.64 + row * 0.14 + col * 0.07
        feather(f"Covert_{row}_{col}", (bx, -0.1 - row * 0.018, bz),
                (bx + length * 0.7, -0.1, bz - length * 0.58), 0.42 - row * 0.045,
                [PURPLE, LILAC, MIDNIGHT, PURPLE][(row + col) % 4], wing, depth=0.095)

for i in range(7):
    base = (0.14 + i * 0.11, -0.02, 0.24 - i * 0.065)
    tip = (1.12 + i * 0.13, -0.02, -0.62 - i * 0.1)
    feather(f"Primary_{i}", base, tip, 0.34 - i * 0.012,
            [INK, MIDNIGHT, PURPLE][i % 3], wing, depth=0.08)

# Mirrored far wing keeps silhouette complete when raven turns around.
ico("WingBackMass", (0.3, 0, 0.18), (0.75, 0.24, 0.94), INK, wing_back, subdivisions=1, rotation=(0, -0.1, -0.35))
for row in range(2):
    for col in range(4):
        bx = -0.12 + col * 0.31 + row * 0.08
        bz = 0.63 - row * 0.34 - col * 0.085
        length = 0.64 + row * 0.14 + col * 0.065
        feather(f"BackCovert_{row}_{col}", (bx, 0.08, bz),
                (bx + length * 0.7, 0.08, bz - length * 0.58), 0.39 - row * 0.04,
                [MIDNIGHT, PURPLE, INK][(row + col) % 3], wing_back, depth=0.085)

# Wedge/fan tail with layered central rectrices.
for i in range(7):
    offset = i - 3
    feather(f"TailFeather_{i}", (0.03, 0.06 * offset, 0.1),
            (1.4 + 0.1 * (3 - abs(offset)), 0.06 * offset, -1.18 - abs(offset) * 0.07),
            0.33, [INK, MIDNIGHT, PURPLE][i % 3], tail, depth=0.075)

# Chest fringe adds low-poly layered silhouette.
for i in range(5):
    feather(f"ChestFeather_{i}", (-0.5 + i * 0.16, -0.34, -0.08 - i * 0.12),
            (-0.5 + i * 0.19, -0.34, -0.62 - i * 0.08), 0.3,
            [MIDNIGHT, PURPLE, INK][i % 3], body, depth=0.085)


def build_leg(group, front=True):
    cylinder("Shin", (0, 0, -0.25), 0.055, 0.58, LEG, group, rotation=(0, 0.12 if front else -0.08, 0))
    cylinder("Ankle", (-0.03, 0, -0.58), 0.045, 0.32, LEG, group, rotation=(0, -0.12, 0))
    for i, y in enumerate((-0.12, 0, 0.12)):
        cylinder(f"Toe_{i}", (-0.2, y, -0.76), 0.026, 0.48 - abs(i - 1) * 0.05, LEG, group,
                 rotation=(0, math.pi / 2 + (i - 1) * 0.11, 0), vertices=4)
        cone(f"Claw_{i}", (-0.45, y, -0.78), 0.045, 0.18, BEAK, group,
             rotation=(0, -math.pi / 2, 0), vertices=4)
    cylinder("RearToe", (0.13, 0.02, -0.74), 0.024, 0.31, LEG, group, rotation=(0, -math.pi / 2, 0), vertices=4)
    cone("RearClaw", (0.31, 0.02, -0.75), 0.04, 0.15, BEAK, group, rotation=(0, math.pi / 2, 0), vertices=4)


build_leg(leg_front, True)
build_leg(leg_back, False)

for obj in bpy.context.scene.objects:
    obj.select_set(True)

OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=str(OUT),
    export_format="GLB",
    export_apply=True,
    export_yup=True,
    export_materials="EXPORT",
    export_animations=False,
)
print(f"Wrote {OUT}")
