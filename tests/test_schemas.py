"""schemas 모듈 단위 테스트 — Pydantic 검증 로직."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from gempygen.schemas import (
    Borehole,
    BoreholeLayer,
    GeoModelInput,
    ModelExtent,
    ModelResolution,
    Orientation,
    StructuralGroupConfig,
)


# ── ModelExtent ────────────────────────────────────────


class TestModelExtent:
    def test_valid_extent(self):
        extent = ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0)
        assert extent.to_list() == [0, 100, 0, 100, -300, 0]

    def test_rejects_x_min_gte_x_max(self):
        with pytest.raises(PydanticValidationError, match="x_min"):
            ModelExtent(x_min=100, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0)

    def test_rejects_y_min_gte_y_max(self):
        with pytest.raises(PydanticValidationError, match="y_min"):
            ModelExtent(x_min=0, x_max=100, y_min=200, y_max=100, z_min=-300, z_max=0)

    def test_rejects_z_min_gte_z_max(self):
        with pytest.raises(PydanticValidationError, match="z_min"):
            ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=0, z_max=-300)


# ── ModelResolution ────────────────────────────────────


class TestModelResolution:
    def test_defaults_50x50x50(self):
        res = ModelResolution()
        assert res.to_list() == [50, 50, 50]

    def test_rejects_zero(self):
        with pytest.raises(PydanticValidationError):
            ModelResolution(nx=0)

    def test_rejects_negative(self):
        with pytest.raises(PydanticValidationError):
            ModelResolution(ny=-1)

    def test_rejects_over_200(self):
        with pytest.raises(PydanticValidationError):
            ModelResolution(nz=201)


# ── Orientation ────────────────────────────────────────


class TestOrientation:
    def test_accepts_angles(self):
        ori = Orientation(x=0, y=0, z=0, azimuth=45, dip=30, polarity=1)
        assert ori.azimuth == 45

    def test_accepts_pole_vector(self):
        ori = Orientation(x=0, y=0, z=0, gx=0.1, gy=0.2, gz=0.97)
        assert ori.gx == 0.1

    def test_rejects_missing_both(self):
        with pytest.raises(PydanticValidationError, match="azimuth.*dip.*polarity.*gx.*gy.*gz"):
            Orientation(x=0, y=0, z=0)


# ── Borehole ──────────────────────────────────────────


class TestBorehole:
    def test_valid_borehole(self):
        bh = Borehole(x=0, y=0, layers=[BoreholeLayer(element="Sand", z=-100)])
        assert len(bh.layers) == 1

    def test_rejects_empty_layers(self):
        with pytest.raises(PydanticValidationError):
            Borehole(x=0, y=0, layers=[])


# ── BoreholeLayer ─────────────────────────────────────


class TestBoreholeLayer:
    def test_rejects_empty_element(self):
        with pytest.raises(PydanticValidationError):
            BoreholeLayer(element="", z=-100)


# ── GeoModelInput ─────────────────────────────────────


class TestGeoModelInput:
    @pytest.fixture()
    def minimal_input(self):
        return GeoModelInput(
            extent=ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0),
            boreholes=[
                Borehole(x=0, y=0, layers=[
                    BoreholeLayer(element="Sandstone", z=-100),
                    BoreholeLayer(element="Limestone", z=-200),
                ]),
                Borehole(x=100, y=0, layers=[
                    BoreholeLayer(element="Sandstone", z=-120),
                ]),
            ],
        )

    def test_discover_elements_preserves_order(self, minimal_input):
        elements = minimal_input.discover_elements()
        assert elements == ["Sandstone", "Limestone"]

    def test_discover_elements_no_duplicates(self, minimal_input):
        elements = minimal_input.discover_elements()
        assert len(elements) == len(set(elements))

    def test_group_points_by_element(self, minimal_input):
        groups = minimal_input.group_points_by_element()
        assert "Sandstone" in groups
        assert "Limestone" in groups
        assert len(groups["Sandstone"]) == 2  # 2 boreholes have Sandstone
        assert len(groups["Limestone"]) == 1  # 1 borehole has Limestone

    def test_resolve_structural_groups_default(self, minimal_input):
        groups = minimal_input.resolve_structural_groups()
        assert len(groups) == 1
        assert groups[0].name == "Default"
        assert groups[0].elements == ["Sandstone", "Limestone"]
        assert groups[0].relation == "erode"

    def test_resolve_structural_groups_explicit(self):
        input_data = GeoModelInput(
            extent=ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0),
            boreholes=[
                Borehole(x=0, y=0, layers=[BoreholeLayer(element="Sand", z=-100)]),
            ],
            structural_groups=[
                StructuralGroupConfig(name="G1", elements=["Sand"], relation="erode"),
            ],
        )
        groups = input_data.resolve_structural_groups()
        assert len(groups) == 1
        assert groups[0].name == "G1"

    def test_rejects_empty_boreholes(self):
        with pytest.raises(PydanticValidationError):
            GeoModelInput(
                extent=ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0),
                boreholes=[],
            )
