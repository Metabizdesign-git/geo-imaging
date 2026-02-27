"""exporters 모듈 단위 테스트 — 단면 경계선 추출."""

from __future__ import annotations

import numpy as np
import pytest

from gempygen.exporters import to_section_json
from gempygen.schemas import LithologyStats, ModelResult

# ── Fixtures ──────────────────────────────────────────


@pytest.fixture()
def voxel_result():
    """4×3×2 voxel grid을 포함하는 ModelResult."""
    nx, ny, nz = 4, 3, 2
    # 간단한 2-layer 모델: z=0 → id=1, z=1 → id=2
    block = np.zeros(nx * ny * nz, dtype=float)
    grid = block.reshape(nx, ny, nz)
    grid[:, :, 0] = 1  # 하부
    grid[:, :, 1] = 2  # 상부
    return ModelResult(
        lith_block=block,
        scalar_field_matrix=np.array([[0.0]]),
        lithology_stats=[
            LithologyStats(id=1, element_name="Sandstone", cell_count=12, ratio=0.5),
            LithologyStats(id=2, element_name="Limestone", cell_count=12, ratio=0.5),
        ],
        total_cells=nx * ny * nz,
        resolution=[nx, ny, nz],
        extent=[0, 100, 0, 60, -200, 0],
        element_names=["Sandstone", "Limestone"],
    )


# ── to_section_json ──────────────────────────────────


class TestToSectionJson:
    def test_xz_returns_boundaries(self, voxel_result):
        data = to_section_json(voxel_result, axis="xz")
        assert data["axis"] == "xz"
        assert data["position"] == 30.0  # (0 + 60) / 2
        assert data["h_axis"] == "x"
        assert data["v_axis"] == "z"
        # 2-layer 모델이므로 경계선 1개
        assert len(data["boundaries"]) == 1
        bd = data["boundaries"][0]
        assert bd["upper"] == "Limestone"
        assert bd["lower"] == "Sandstone"
        # 압축: v값이 동일한 수평 구간 → 첫/끝 점만 유지 (4→2)
        assert len(bd["points"]) == 2
        # 각 점은 [h, v] 좌표
        assert len(bd["points"][0]) == 2

    def test_yz_section(self, voxel_result):
        data = to_section_json(voxel_result, axis="yz", position=50.0)
        assert data["axis"] == "yz"
        assert data["h_axis"] == "y"
        assert len(data["boundaries"]) == 1

    def test_xy_section(self, voxel_result):
        data = to_section_json(voxel_result, axis="xy", position=-100.0)
        assert data["h_axis"] == "x"
        assert data["v_axis"] == "y"

    def test_layers_contain_elements(self, voxel_result):
        data = to_section_json(voxel_result, axis="xz")
        assert "Sandstone" in data["layers"]
        assert "Limestone" in data["layers"]

    def test_json_serializable(self, voxel_result):
        import json
        data = to_section_json(voxel_result, axis="xz")
        serialized = json.dumps(data)
        assert isinstance(serialized, str)

    def test_invalid_axis_raises(self, voxel_result):
        with pytest.raises(ValueError, match="'xz', 'yz', 'xy'"):
            to_section_json(voxel_result, axis="invalid")

    def test_position_out_of_range_raises(self, voxel_result):
        with pytest.raises(ValueError, match="벗어남"):
            to_section_json(voxel_result, axis="xz", position=999.0)

    def test_boundary_points_sorted_by_h(self, voxel_result):
        data = to_section_json(voxel_result, axis="xz")
        for bd in data["boundaries"]:
            h_values = [p[0] for p in bd["points"]]
            assert h_values == sorted(h_values)
