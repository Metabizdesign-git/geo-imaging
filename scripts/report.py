import numpy as np

from gempygen.schemas import GeoModelInput, ModelResult


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


def print_input_summary(input_data: GeoModelInput):
    """GeoModelInput 기반 입력 요약을 출력한다."""
    # Boreholes (Surface Points)
    print("\n" + "=" * 60)
    print("  INPUT: Boreholes (Surface Points)")
    print("=" * 60)
    total_points = sum(len(bh.layers) for bh in input_data.boreholes)
    print(f"  {len(input_data.boreholes)} boreholes, {total_points} points\n")
    rows = []
    idx = 0
    for bh in input_data.boreholes:
        for layer in bh.layers:
            idx += 1
            rows.append([idx, f"{bh.x:.0f}", f"{bh.y:.0f}", f"{layer.z:.0f}", layer.element])
    print_table(["#", "X", "Y", "Z", "Element"], rows)

    # Structural Groups
    print("\n" + "=" * 60)
    print("  INPUT: Structural Groups")
    print("=" * 60)
    groups = input_data.resolve_structural_groups()
    for gc in groups:
        print(f"  {gc.name} ({gc.relation}): {', '.join(gc.elements)}")

    # Grid
    print("\n" + "=" * 60)
    print("  INPUT: Grid")
    print("=" * 60)
    res = input_data.resolution
    ext = input_data.extent
    print(f"  Resolution: {res.nx} x {res.ny} x {res.nz} = {res.nx * res.ny * res.nz:,} cells")
    print(f"  X: [{ext.x_min}, {ext.x_max}]  Y: [{ext.y_min}, {ext.y_max}]  Z: [{ext.z_min}, {ext.z_max}]")


def print_output_summary(result: ModelResult):
    """ModelResult 기반 출력 요약을 출력한다."""
    # Lithology Block
    print("\n" + "=" * 60)
    print("  OUTPUT: Lithology Block")
    print("=" * 60)
    n_unique = len(result.lithology_stats)
    print(f"  {result.total_cells:,} cells -> {n_unique} lithologies\n")
    print_table(
        ["ID", "Name", "Cells", "Ratio"],
        [[s.id, s.element_name, f"{s.cell_count:,}", f"{s.ratio * 100:.1f}%"]
         for s in result.lithology_stats]
    )

    # Scalar Field
    print("\n" + "=" * 60)
    print("  OUTPUT: Scalar Field")
    print("=" * 60)
    sf = result.scalar_field_matrix
    print(f"  shape: {sf.shape}  (groups x cells)")
    print(f"  range: [{sf.min():.2f}, {sf.max():.2f}]")


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    from gempygen import GeoModelBuilder, BoreholeLayer

    builder = (
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
    )

    input_data = builder.to_input()
    print_input_summary(input_data)

    result = builder.build_and_compute()
    print_output_summary(result)
