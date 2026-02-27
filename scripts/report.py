import numpy as np


def print_table(headers, rows, col_widths=None):
    if col_widths is None:
        col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2
                      for i in range(len(headers))]
    sep = "+" + "+".join("-" * w for w in col_widths) + "+"

    def fmt_row(row):
        return "|" + "|".join(str(row[i]).center(w) for i, w in enumerate(col_widths)) + "|"

    print(sep)
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))
    print(sep)


def _build_id_to_name(geo_model) -> dict:
    """structural_frame에서 element id → name 매핑을 구축한다."""
    id_to_name = {}
    for group in geo_model.structural_frame.structural_groups:
        for elem in group.elements:
            if hasattr(elem, 'id') and elem.id is not None:
                id_to_name[elem.id] = elem.name
            else:
                id_to_name[elem.name] = elem.name
    return id_to_name


def _resolve_element_name(record_id, id_to_name: dict, fallback: str = "Unknown") -> str:
    """레코드 id로부터 element 이름을 찾는다."""
    return id_to_name.get(record_id, fallback)


def print_input_summary(geo_model):
    id_to_name = _build_id_to_name(geo_model)

    # Surface Points
    print("\n" + "=" * 60)
    print("  INPUT: Surface Points")
    print("=" * 60)
    sp = geo_model.surface_points_copy
    print(f"  {sp.data.shape[0]} points\n")
    print_table(
        ["#", "X", "Y", "Z", "Element"],
        [[i + 1, f"{r['X']:.0f}", f"{r['Y']:.0f}", f"{r['Z']:.0f}",
          _resolve_element_name(r['id'], id_to_name)]
         for i, r in enumerate(sp.data)]
    )

    # Orientations
    print("\n" + "=" * 60)
    print("  INPUT: Orientations")
    print("=" * 60)
    ori = geo_model.orientations_copy
    print(f"  {ori.data.shape[0]} orientations\n")
    print_table(
        ["#", "X", "Y", "Z", "G_x", "G_y", "G_z", "Element"],
        [[i + 1, f"{r['X']:.0f}", f"{r['Y']:.0f}", f"{r['Z']:.0f}",
          f"{r['G_x']:.4f}", f"{r['G_y']:.4f}", f"{r['G_z']:.4f}",
          _resolve_element_name(r['id'], id_to_name)]
         for i, r in enumerate(ori.data)]
    )

    # Grid
    print("\n" + "=" * 60)
    print("  INPUT: Grid")
    print("=" * 60)
    grid = geo_model.grid.regular_grid
    res = grid.resolution
    extent = geo_model.grid.extent
    print(f"  Resolution: {res[0]} x {res[1]} x {res[2]} = {grid.values.shape[0]:,} cells")
    print(f"  X: [{extent[0]}, {extent[1]}]  Y: [{extent[2]}, {extent[3]}]  Z: [{extent[4]}, {extent[5]}]")


def print_output_summary(geo_model):
    sol = geo_model.solutions
    raw = sol.raw_arrays

    # Lithology Block
    print("\n" + "=" * 60)
    print("  OUTPUT: Lithology Block")
    print("=" * 60)
    if raw is not None:
        unique, counts = np.unique(raw.lith_block, return_counts=True)
        element_names = [
            e.name
            for g in geo_model.structural_frame.structural_groups
            for e in g.elements
        ]
        all_names = element_names + ["Basement"]
        lith_names = {i + 1: name for i, name in enumerate(all_names)}
        total = raw.lith_block.shape[0]
        print(f"  {total:,} cells -> {len(unique)} lithologies\n")
        print_table(
            ["ID", "Name", "Cells", "Ratio"],
            [[int(u), lith_names.get(int(u), f"Unknown({int(u)})"),
              f"{c:,}", f"{c / total * 100:.1f}%"]
             for u, c in zip(unique, counts)]
        )

    # Scalar Field
    print("\n" + "=" * 60)
    print("  OUTPUT: Scalar Field")
    print("=" * 60)
    if raw is not None:
        sf = raw.scalar_field_matrix
        print(f"  shape: {sf.shape}  (groups x cells)")
        print(f"  range: [{sf.min():.2f}, {sf.max():.2f}]")


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    from gempygen import GeoModelBuilder, BoreholeLayer
    from gempygen.engine import build_gempy_model, compute_gempy_model

    input_data = (
        GeoModelBuilder("simple_model")
        .set_extent(0, 100, 0, 100, -300, 0)
        .set_resolution(50, 50, 50)
        .add_borehole(0, 0, [
            BoreholeLayer(element="Sandstone", z=-100),
            BoreholeLayer(element="Limestone", z=-200),
        ])
        .add_borehole(100, 0, [
            BoreholeLayer(element="Sandstone", z=-120),
            BoreholeLayer(element="Limestone", z=-220),
        ])
        .add_borehole(0, 100, [
            BoreholeLayer(element="Sandstone", z=-110),
            BoreholeLayer(element="Limestone", z=-210),
        ])
        .to_input()
    )

    geo_model = build_gempy_model(input_data)
    print_input_summary(geo_model)
    compute_gempy_model(geo_model)
    print_output_summary(geo_model)
