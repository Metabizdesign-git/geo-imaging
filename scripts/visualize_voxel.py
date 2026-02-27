import matplotlib
matplotlib.use('Agg')

from pathlib import Path

import matplotlib.pyplot as plt
import pyvista as pv
import gempy_viewer as gpv


def save_2d_sections(geo_model, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    p2d = gpv.plot_2d(
        geo_model,
        cell_number='mid',
        show_data=True,
        show_lith=True,
        show=False,
    )
    p2d.fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(p2d.fig)
    print(f"  [1/2] 2D sections saved: {output_path}")


def save_3d_surfaces(geo_model, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pv.OFF_SCREEN = True

    gempy_vista = gpv.plot_3d(
        geo_model,
        show_surfaces=True,
        show_data=True,
        show_lith=True,
        image=False,
    )

    gempy_vista.p.screenshot(output_path)
    gempy_vista.p.close()
    print(f"  [2/2] 3D surfaces saved: {output_path}")


if __name__ == "__main__":
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
        # Sandstone 단일 시추공 — 전역 분포
        .add_borehole(50, 50, [BoreholeLayer(element="Sandstone", z=-105)])
        .add_borehole(25, 25, [BoreholeLayer(element="Sandstone", z=-110)])
        .add_borehole(75, 25, [BoreholeLayer(element="Sandstone", z=-90)])
        .add_borehole(25, 75, [BoreholeLayer(element="Sandstone", z=-95)])
        .add_borehole(75, 75, [BoreholeLayer(element="Sandstone", z=-115)])
        .to_input()
    )

    geo_model = build_gempy_model(input_data)
    compute_gempy_model(geo_model)

    save_2d_sections(geo_model, "results/result_2d_sections.png")
    save_3d_surfaces(geo_model, "results/result_3d_surfaces.png")

    print("\n  Done!")
