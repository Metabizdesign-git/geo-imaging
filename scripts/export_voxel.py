"""Voxel 데이터를 디스크에 저장하는 스크립트.

raw_arrays(lith_block, scalar_field_matrix)를 가공 없이 그대로 .npz로 저장한다.
"""

import argparse
from pathlib import Path

import numpy as np


def export_raw(geo_model, output_path: str) -> None:
    """geo_model.solutions.raw_arrays를 그대로 .npz로 저장한다.

    저장 내용:
        lith_block           : 1D float 배열 (total_cells,)
        scalar_field_matrix  : 2D float 배열 (n_groups, total_cells)
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    raw = geo_model.solutions.raw_arrays
    np.savez_compressed(
        path,
        lith_block=raw.lith_block,
        scalar_field_matrix=raw.scalar_field_matrix,
    )
    print(f"  saved: {path}  ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    from gempygen import GeoModelBuilder, BoreholeLayer
    from gempygen.engine import build_gempy_model, compute_gempy_model

    parser = argparse.ArgumentParser(description="Voxel raw 데이터를 디스크에 저장")
    parser.add_argument("-o", "--output", default="results/voxel_raw.npz", help="출력 경로 (default: results/voxel_raw.npz)")
    args = parser.parse_args()

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
    compute_gempy_model(geo_model)
    export_raw(geo_model, args.output)

    print("\n  Done!")
