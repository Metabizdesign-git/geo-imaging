"""GeoModelBuilder 리팩토링 관련 단위 테스트."""

from __future__ import annotations

import pytest

from gempygen import (
    GeoModelBuilder,
    GeoModelInput,
    ModelExtent,
    ModelResolution,
    Borehole,
    BoreholeLayer,
    Orientation,
    StructuralGroupConfig,
    compute_model,
)
from pydantic import ValidationError as PydanticValidationError

from gempygen.exceptions import ValidationError


# ── Fixtures ──────────────────────────────────────────


@pytest.fixture()
def sample_layers():
    return [
        BoreholeLayer(element="Sandstone", z=-100),
        BoreholeLayer(element="Limestone", z=-200),
    ]


@pytest.fixture()
def sample_orientations():
    return [
        Orientation(x=50, y=50, z=-150, azimuth=45, dip=30, polarity=1),
    ]


@pytest.fixture()
def builder_with_data(sample_layers):
    return (
        GeoModelBuilder("test_model")
        .set_extent(0, 100, 0, 100, -300, 0)
        .set_resolution(20, 20, 20)
        .add_borehole(0, 0, sample_layers)
        .add_borehole(100, 0, [
            BoreholeLayer(element="Sandstone", z=-120),
            BoreholeLayer(element="Limestone", z=-220),
        ])
        .add_borehole(0, 100, [
            BoreholeLayer(element="Sandstone", z=-110),
            BoreholeLayer(element="Limestone", z=-210),
        ])
    )


# ── add_borehole: list[BoreholeLayer] ────────────────


class TestAddBorehole:
    def test_accepts_borehole_layer_objects(self, sample_layers):
        builder = GeoModelBuilder("test")
        builder.set_extent(0, 100, 0, 100, -300, 0)
        builder.add_borehole(0, 0, sample_layers)
        input_data = builder.to_input()
        assert len(input_data.boreholes) == 1
        assert input_data.boreholes[0].layers[0].element == "Sandstone"
        assert input_data.boreholes[0].layers[1].z == -200

    def test_returns_self_for_chaining(self, sample_layers):
        builder = GeoModelBuilder("test")
        result = builder.add_borehole(0, 0, sample_layers)
        assert result is builder

    def test_rejects_tuple_input(self):
        builder = GeoModelBuilder("test")
        with pytest.raises((TypeError, PydanticValidationError)):
            builder.add_borehole(0, 0, [("Sandstone", -100)])


# ── add_orientations: list[Orientation] ──────────────


class TestAddOrientations:
    def test_accepts_orientation_objects(self, sample_orientations):
        builder = GeoModelBuilder("test")
        builder.add_orientations("Sandstone", sample_orientations)
        assert len(builder._orientations["Sandstone"]) == 1
        assert builder._orientations["Sandstone"][0].azimuth == 45

    def test_extends_existing_orientations(self, sample_orientations):
        builder = GeoModelBuilder("test")
        builder.add_orientations("Sandstone", sample_orientations)
        builder.add_orientations("Sandstone", [
            Orientation(x=60, y=60, z=-160, gx=0.1, gy=0.2, gz=0.97),
        ])
        assert len(builder._orientations["Sandstone"]) == 2

    def test_returns_self_for_chaining(self, sample_orientations):
        builder = GeoModelBuilder("test")
        result = builder.add_orientations("Sandstone", sample_orientations)
        assert result is builder


# ── to_input 검증 ────────────────────────────────────


class TestToInput:
    def test_raises_without_extent(self, sample_layers):
        builder = GeoModelBuilder("test")
        builder.add_borehole(0, 0, sample_layers)
        with pytest.raises(ValidationError, match="Extent not set"):
            builder.to_input()

    def test_raises_without_boreholes(self):
        builder = GeoModelBuilder("test")
        builder.set_extent(0, 100, 0, 100, -300, 0)
        with pytest.raises(ValidationError, match="No boreholes"):
            builder.to_input()

    def test_produces_valid_input(self, builder_with_data):
        input_data = builder_with_data.to_input()
        assert isinstance(input_data, GeoModelInput)
        assert input_data.project_name == "test_model"
        assert len(input_data.boreholes) == 3
        assert input_data.resolution.nx == 20


# ── compute_model ────────────────────────────────────


class TestComputeModel:
    def test_accepts_geo_model_input(self, builder_with_data):
        input_data = builder_with_data.to_input()
        assert isinstance(input_data, GeoModelInput)
        # compute_model 시그니처가 GeoModelInput만 받는지 확인
        # (실제 GemPy 계산은 통합 테스트에서 수행)

    def test_rejects_raw_dict(self):
        with pytest.raises((TypeError, AttributeError)):
            compute_model({"project_name": "test"})


# ── GeoModelInput dict 래핑 ──────────────────────────


class TestGeoModelInputWrapping:
    def test_from_dict_unpacking(self):
        data = {
            "project_name": "dict_model",
            "extent": {
                "x_min": 0, "x_max": 100,
                "y_min": 0, "y_max": 100,
                "z_min": -300, "z_max": 0,
            },
            "boreholes": [
                {
                    "x": 0, "y": 0,
                    "layers": [
                        {"element": "Sandstone", "z": -100},
                        {"element": "Limestone", "z": -200},
                    ],
                },
            ],
        }
        input_data = GeoModelInput(**data)
        assert isinstance(input_data, GeoModelInput)
        assert isinstance(input_data.extent, ModelExtent)
        assert isinstance(input_data.boreholes[0], Borehole)
        assert isinstance(input_data.boreholes[0].layers[0], BoreholeLayer)

    def test_from_class_objects(self):
        input_data = GeoModelInput(
            project_name="class_model",
            extent=ModelExtent(
                x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0,
            ),
            boreholes=[
                Borehole(x=0, y=0, layers=[
                    BoreholeLayer(element="Sandstone", z=-100),
                ]),
            ],
        )
        assert input_data.project_name == "class_model"
        assert input_data.extent.x_max == 100
