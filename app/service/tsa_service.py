import math

def calculate_surface_area(dimensions: list) -> float:
    dim_map = {d['id']: d['value'] for d in dimensions if d['value'] is not None}
    pi = math.pi

    outer_cylindrical_surface = pi * dim_map['dim_outer_dia'] * dim_map['dim_face_width']
    gear_root_surface = pi * dim_map['dim_gear_root_dia'] * dim_map['dim_face_width']
    hub_lateral_surface = pi * dim_map['dim_hub_dia'] * dim_map['dim_hub_height']
    bore_surface = pi * dim_map['dim_bore'] * dim_map['dim_hub_height']

    outer_radius = dim_map['dim_outer_dia'] / 2
    bore_radius = dim_map['dim_bore'] / 2
    face_area_one_side = pi * (outer_radius ** 2 - bore_radius ** 2)
    flat_faces_total = 2 * face_area_one_side

    total_surface_area = (
        outer_cylindrical_surface
        + gear_root_surface
        + hub_lateral_surface
        + bore_surface
        + flat_faces_total
    )

    return round(total_surface_area, 2)
