"""Voxel 데이터를 디스크에 저장하는 스크립트.

raw_arrays(lith_block, scalar_field_matrix)를 가공 없이 그대로 .npz로 저장한다.
"""

import argparse
from pathlib import Path

import numpy as np

from gempygen.schemas import ModelResult


def export_raw(result: ModelResult, output_path: str) -> None:
    """ModelResult의 lith_block과 scalar_field_matrix를 .npz로 저장한다.

    저장 내용:
        lith_block           : 1D float 배열 (total_cells,)
        scalar_field_matrix  : 2D float 배열 (n_groups, total_cells)
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        path,
        lith_block=result.lith_block,
        scalar_field_matrix=result.scalar_field_matrix,
    )
    print(f"  saved: {path}  ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    from gempygen import GeoModelBuilder, BoreholeLayer

    parser = argparse.ArgumentParser(description="Voxel raw 데이터를 디스크에 저장")
    parser.add_argument("-o", "--output", default="results/voxel_raw.npz", help="출력 경로 (default: results/voxel_raw.npz)")
    args = parser.parse_args()

    result = (
        GeoModelBuilder("simple_model")
        .set_extent(0, 100, 0, 100, -300, 0)
        .set_resolution(50, 50, 50)
        # 2-layer 시추공 (Sandstone + Limestone)
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
        .build_and_compute()
    )

    export_raw(result, args.output)
    print("\n  Done!")
