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
        .set_extent(0, 100, 0, 100, -100, 0)
        .set_resolution(50, 50, 50)
        .add_borehole(0, 0, [
            BoreholeLayer(element="Sandstone", z=-10),
            BoreholeLayer(element="Groundwater", z=-15),
            BoreholeLayer(element="Limestone", z=-30),
            BoreholeLayer(element="Stone1", z=-40),
            BoreholeLayer(element="Stone2", z=-50),
        ])
        .add_borehole(100, 0, [
            #BoreholeLayer(element="Sandstone", z=-3),
            BoreholeLayer(element="Groundwater", z=-15),
            BoreholeLayer(element="Limestone", z=-9),
            BoreholeLayer(element="Stone1", z=-12),
            BoreholeLayer(element="Stone2", z=-15),
        ])
        .to_input()
    )

    geo_model = build_gempy_model(input_data)
    compute_gempy_model(geo_model)

    save_2d_sections(geo_model, "results/result_2d_sections.png")
    save_3d_surfaces(geo_model, "results/result_3d_surfaces.png")

    print("\n  Done!")
