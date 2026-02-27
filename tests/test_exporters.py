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


class TestExcludeBasement:
    """exclude_basement 옵션 테스트."""

    @pytest.fixture()
    def three_layer_result(self):
        """3-layer voxel: id=1(Sandstone), id=2(Limestone), id=3(Basement)."""
        nx, ny, nz = 4, 3, 3
        block = np.zeros(nx * ny * nz, dtype=float)
        grid = block.reshape(nx, ny, nz)
        grid[:, :, 0] = 3  # 최하부 — Basement
        grid[:, :, 1] = 1  # 중간 — Sandstone
        grid[:, :, 2] = 2  # 상부 — Limestone
        return ModelResult(
            lith_block=block,
            scalar_field_matrix=np.array([[0.0]]),
            lithology_stats=[
                LithologyStats(id=1, element_name="Sandstone", cell_count=12, ratio=1 / 3),
                LithologyStats(id=2, element_name="Limestone", cell_count=12, ratio=1 / 3),
                LithologyStats(id=3, element_name="Basement", cell_count=12, ratio=1 / 3),
            ],
            total_cells=nx * ny * nz,
            resolution=[nx, ny, nz],
            extent=[0, 100, 0, 60, -300, 0],
            element_names=["Sandstone", "Limestone"],
        )

    def test_exclude_basement_default(self, three_layer_result):
        """기본값(exclude_basement=True)이면 lower=Basement 경계가 제외된다."""
        data = to_section_json(three_layer_result, axis="xz")
        lowers = [bd["lower"] for bd in data["boundaries"]]
        assert "Basement" not in lowers
        assert "Basement" not in data["layers"]
        # Sandstone/Limestone 경계는 남아있어야 한다
        assert len(data["boundaries"]) == 1

    def test_include_basement_explicit(self, three_layer_result):
        """exclude_basement=False이면 Basement 경계도 포함된다."""
        data = to_section_json(three_layer_result, axis="xz", exclude_basement=False)
        lowers = [bd["lower"] for bd in data["boundaries"]]
        assert "Basement" in lowers
        assert "Basement" in data["layers"]
        assert len(data["boundaries"]) == 2

    def test_exclude_basement_case_insensitive(self):
        """소문자 'basement'도 필터링된다."""
        nx, ny, nz = 4, 3, 3
        block = np.zeros(nx * ny * nz, dtype=float)
        grid = block.reshape(nx, ny, nz)
        grid[:, :, 0] = 3
        grid[:, :, 1] = 1
        grid[:, :, 2] = 2
        result = ModelResult(
            lith_block=block,
            scalar_field_matrix=np.array([[0.0]]),
            lithology_stats=[
                LithologyStats(id=1, element_name="Sandstone", cell_count=12, ratio=1 / 3),
                LithologyStats(id=2, element_name="Limestone", cell_count=12, ratio=1 / 3),
                LithologyStats(id=3, element_name="basement", cell_count=12, ratio=1 / 3),
            ],
            total_cells=nx * ny * nz,
            resolution=[nx, ny, nz],
            extent=[0, 100, 0, 60, -300, 0],
            element_names=["Sandstone", "Limestone"],
        )
        data = to_section_json(result, axis="xz")
        all_names = [bd["lower"] for bd in data["boundaries"]] + [bd["upper"] for bd in data["boundaries"]]
        assert "basement" not in all_names
        assert "basement" not in data["layers"]

    def test_no_stdout_on_exclude_basement(self, three_layer_result, capsys):
        """exclude_basement=True일 때 stdout에 아무것도 출력되지 않는다."""
        to_section_json(three_layer_result, axis="xz", exclude_basement=True)
        captured = capsys.readouterr()
        assert captured.out == ""


class TestModelResultMethods:
    """ModelResult 편의 메서드 테스트."""

    @pytest.fixture()
    def voxel_result(self):
        nx, ny, nz = 4, 3, 2
        block = np.zeros(nx * ny * nz, dtype=float)
        grid = block.reshape(nx, ny, nz)
        grid[:, :, 0] = 1
        grid[:, :, 1] = 2
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

    def test_to_section_json_method_matches_standalone(self, voxel_result):
        """result.to_section_json()이 standalone 함수와 동일한 결과를 반환한다."""
        method_result = voxel_result.to_section_json(axis="xz")
        standalone_result = to_section_json(voxel_result, axis="xz")
        assert method_result == standalone_result

    def test_to_dict_json_serializable(self, voxel_result):
        """to_dict() 반환값이 JSON 직렬화 가능하다."""
        import json
        d = voxel_result.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        assert "lith_block" not in d

    def test_to_dict_with_raw(self, voxel_result):
        """include_raw=True이면 lith_block이 list로 포함된다."""
        d = voxel_result.to_dict(include_raw=True)
        assert "lith_block" in d
        assert isinstance(d["lith_block"], list)
