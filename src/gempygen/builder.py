"""GeoModelBuilder — 지질 모델 생성을 위한 메인 API.

시추공(borehole) 기반 입력으로 직관적인 데이터 구성을 지원한다.

Usage (builder pattern)::

    from gempygen import GeoModelBuilder, BoreholeLayer

    result = (
        GeoModelBuilder("my_model")
        .set_extent(0, 100, 0, 100, -300, 0)
        .add_borehole(0, 0, [BoreholeLayer(element="Sandstone", z=-100), BoreholeLayer(element="Limestone", z=-200)])
        .add_borehole(100, 0, [BoreholeLayer(element="Sandstone", z=-120), BoreholeLayer(element="Limestone", z=-220)])
        .add_borehole(0, 100, [BoreholeLayer(element="Sandstone", z=-110), BoreholeLayer(element="Limestone", z=-210)])
        .build_and_compute()
    )

Usage (class-based)::

    from gempygen import compute_model, GeoModelInput, ModelExtent, Borehole, BoreholeLayer

    input_data = GeoModelInput(
        project_name="my_model",
        extent=ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0),
        boreholes=[
            Borehole(x=0, y=0, layers=[
                BoreholeLayer(element="Sandstone", z=-100),
                BoreholeLayer(element="Limestone", z=-200),
            ]),
        ],
    )
    result = compute_model(input_data)
"""

from __future__ import annotations

from typing import Literal, Optional

from .engine import build_gempy_model, compute_gempy_model, extract_result
from .exceptions import ValidationError
from .schemas import (
    Borehole,
    BoreholeLayer,
    GeoModelInput,
    ModelExtent,
    ModelResolution,
    ModelResult,
    Orientation,
    StructuralGroupConfig,
)


class GeoModelBuilder:
    """시추공 기반 지질 모델 빌더."""

    def __init__(self, project_name: str = "geo_model") -> None:
        self._project_name = project_name
        self._extent: Optional[ModelExtent] = None
        self._resolution: ModelResolution = ModelResolution()
        self._boreholes: list[Borehole] = []
        self._structural_groups: Optional[list[StructuralGroupConfig]] = None
        self._orientations: dict[str, list[Orientation]] = {}

    # ── Configuration ──────────────────────────────────

    def set_extent(
        self,
        x_min: float, x_max: float,
        y_min: float, y_max: float,
        z_min: float, z_max: float,
    ) -> GeoModelBuilder:
        """모델의 공간 범위를 설정한다."""
        self._extent = ModelExtent(
            x_min=x_min, x_max=x_max,
            y_min=y_min, y_max=y_max,
            z_min=z_min, z_max=z_max,
        )
        return self

    def set_resolution(
        self, nx: int = 50, ny: int = 50, nz: int = 50,
    ) -> GeoModelBuilder:
        """격자 해상도를 설정한다."""
        self._resolution = ModelResolution(nx=nx, ny=ny, nz=nz)
        return self

    # ── Data ───────────────────────────────────────────

    def add_borehole(
        self, x: float, y: float, layers: list[BoreholeLayer],
    ) -> GeoModelBuilder:
        """시추공 데이터를 추가한다.

        Args:
            x: 시추공 X 좌표
            y: 시추공 Y 좌표
            layers: BoreholeLayer 객체 리스트
                예: [BoreholeLayer(element="Sandstone", z=-100)]
        """
        self._boreholes.append(Borehole(x=x, y=y, layers=layers))
        return self

    # ── Structure (optional) ───────────────────────────

    def set_group(
        self, name: str, elements: list[str],
        relation: Literal["erode", "onlap", "fault", "basement"] = "erode",
    ) -> GeoModelBuilder:
        """구조 그룹을 명시적으로 설정한다. 생략 시 자동 구성된다."""
        if self._structural_groups is None:
            self._structural_groups = []
        self._structural_groups.append(
            StructuralGroupConfig(name=name, elements=elements, relation=relation)
        )
        return self

    def add_orientations(
        self, element_name: str, orientations: list[Orientation],
    ) -> GeoModelBuilder:
        """element에 명시적 방위를 추가한다. 생략 시 자동 추정된다."""
        if element_name not in self._orientations:
            self._orientations[element_name] = []
        self._orientations[element_name].extend(orientations)
        return self

    # ── Build & Compute ────────────────────────────────

    def to_input(self) -> GeoModelInput:
        """축적된 상태를 검증된 GeoModelInput으로 조립한다."""
        if self._extent is None:
            raise ValidationError("Extent not set. Call set_extent() first.")
        if not self._boreholes:
            raise ValidationError("No boreholes. Call add_borehole() first.")

        return GeoModelInput(
            project_name=self._project_name,
            extent=self._extent,
            resolution=self._resolution,
            boreholes=self._boreholes,
            structural_groups=self._structural_groups,
            orientations=self._orientations or None,
        )

    def build_and_compute(self) -> ModelResult:
        """입력 검증 → GemPy 모델 생성 → 계산 → 결과 반환."""
        input_data = self.to_input()
        geo_model = build_gempy_model(input_data)
        compute_gempy_model(geo_model)
        return extract_result(geo_model, input_data)

    @classmethod
    def from_input(cls, input_data: GeoModelInput) -> GeoModelBuilder:
        """GeoModelInput 스키마로부터 빌더를 생성한다."""
        builder = cls(project_name=input_data.project_name)
        builder._extent = input_data.extent
        builder._resolution = input_data.resolution
        builder._boreholes = list(input_data.boreholes)
        builder._structural_groups = input_data.structural_groups
        builder._orientations = dict(input_data.orientations) if input_data.orientations else {}
        return builder


def compute_model(input_data: GeoModelInput) -> ModelResult:
    """GeoModelInput으로부터 지질 모델을 계산한다."""
    return GeoModelBuilder.from_input(input_data).build_and_compute()
