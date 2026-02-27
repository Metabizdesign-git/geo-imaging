from __future__ import annotations

from typing import Optional, Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator


# ── Input Schemas ──────────────────────────────────────────────


class BoreholeLayer(BaseModel):
    """시추공의 단일 깊이에서 관측된 지층."""

    element: str = Field(..., min_length=1)
    z: float


class Borehole(BaseModel):
    """하나의 시추공 — 동일 (x, y) 좌표에서 깊이별 지층 관측.

    Example::

        Borehole(x=0, y=0, layers=[
            BoreholeLayer(element="Sandstone", z=-100),
            BoreholeLayer(element="Limestone", z=-200),
        ])
    """

    x: float
    y: float
    layers: list[BoreholeLayer] = Field(..., min_length=1)


class Orientation(BaseModel):
    """지질 표면의 명시적 방위.

    (azimuth, dip, polarity) 또는 (gx, gy, gz) 중 하나를 제공해야 한다.
    """

    x: float
    y: float
    z: float
    azimuth: Optional[float] = None
    dip: Optional[float] = None
    polarity: Optional[float] = None
    gx: Optional[float] = None
    gy: Optional[float] = None
    gz: Optional[float] = None

    @model_validator(mode="after")
    def _check_orientation_data(self) -> "Orientation":
        has_angles = all(v is not None for v in [self.azimuth, self.dip, self.polarity])
        has_pole = all(v is not None for v in [self.gx, self.gy, self.gz])
        if not has_angles and not has_pole:
            raise ValueError(
                "Provide either (azimuth, dip, polarity) or (gx, gy, gz)"
            )
        return self


class StructuralGroupConfig(BaseModel):
    """구조 그룹 설정. 생략 시 모든 element가 단일 erode 그룹으로 자동 구성된다."""

    name: str = Field(default="Default")
    elements: list[str] = Field(..., min_length=1)
    relation: Literal["erode", "onlap", "fault", "basement"] = "erode"


class ModelExtent(BaseModel):
    """모델의 공간 범위."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    @model_validator(mode="after")
    def _check_bounds(self) -> "ModelExtent":
        if self.x_min >= self.x_max:
            raise ValueError(f"x_min ({self.x_min}) must be < x_max ({self.x_max})")
        if self.y_min >= self.y_max:
            raise ValueError(f"y_min ({self.y_min}) must be < y_max ({self.y_max})")
        if self.z_min >= self.z_max:
            raise ValueError(f"z_min ({self.z_min}) must be < z_max ({self.z_max})")
        return self

    def to_list(self) -> list[float]:
        return [self.x_min, self.x_max, self.y_min, self.y_max, self.z_min, self.z_max]


class ModelResolution(BaseModel):
    """모델 격자 해상도."""

    nx: int = Field(default=50, gt=0, le=200)
    ny: int = Field(default=50, gt=0, le=200)
    nz: int = Field(default=50, gt=0, le=200)

    def to_list(self) -> list[int]:
        return [self.nx, self.ny, self.nz]


class GeoModelInput(BaseModel):
    """지질 모델 생성을 위한 최상위 입력 스키마.

    시추공(borehole) 기반 입력: 각 시추공은 동일 (x, y) 좌표에서
    깊이별로 관측된 지층 데이터를 담는다.

    structural_groups를 생략하면 모든 element가 단일 erode 그룹으로 자동 구성된다.
    orientations를 생략하면 surface points로부터 SVD로 자동 추정된다.
    """

    project_name: str = Field(default="geo_model", min_length=1)
    extent: ModelExtent
    resolution: ModelResolution = Field(default_factory=ModelResolution)
    boreholes: list[Borehole] = Field(..., min_length=1)
    structural_groups: Optional[list[StructuralGroupConfig]] = None
    orientations: Optional[dict[str, list[Orientation]]] = None

    def discover_elements(self) -> list[str]:
        """시추공 데이터에서 element 이름을 등장 순서대로 추출한다."""
        seen: set[str] = set()
        ordered: list[str] = []
        for bh in self.boreholes:
            for layer in bh.layers:
                if layer.element not in seen:
                    seen.add(layer.element)
                    ordered.append(layer.element)
        return ordered

    def resolve_structural_groups(self) -> list[StructuralGroupConfig]:
        """structural_groups가 없으면 자동 생성한다."""
        if self.structural_groups is not None:
            return self.structural_groups
        elements = self.discover_elements()
        return [StructuralGroupConfig(name="Default", elements=elements, relation="erode")]

    def group_points_by_element(self) -> dict[str, list[tuple[float, float, float]]]:
        """시추공 데이터를 element별 (x, y, z) 리스트로 변환한다."""
        result: dict[str, list[tuple[float, float, float]]] = {}
        for bh in self.boreholes:
            for layer in bh.layers:
                if layer.element not in result:
                    result[layer.element] = []
                result[layer.element].append((bh.x, bh.y, layer.z))
        return result


# ── Output Schemas ─────────────────────────────────────────────


class LithologyStats(BaseModel):
    """단일 암상의 통계."""

    id: int
    element_name: str
    cell_count: int
    ratio: float = Field(description="전체 셀 대비 비율 [0.0, 1.0]")


class ModelResult(BaseModel):
    """계산된 지질 모델의 전체 출력."""

    model_config = {"arbitrary_types_allowed": True}

    lith_block: np.ndarray
    scalar_field_matrix: np.ndarray
    lithology_stats: list[LithologyStats] = Field(default_factory=list)
    total_cells: int
    resolution: list[int]
    extent: list[float]
    element_names: list[str]

    def to_section_json(
        self,
        axis: Literal["xz", "yz", "xy"] = "xz",
        position: float | None = None,
        exclude_basement: bool = True,
    ) -> dict:
        """단면 경계선을 JSON-serializable dict로 추출한다.

        Args:
            axis: 단면 방향 (``"xz"``, ``"yz"``, ``"xy"``).
            position: 절단 위치 (실제 좌표). 생략 시 중앙값 사용.
            exclude_basement: True이면 Basement 경계를 제외한다.
        """
        from .exporters import to_section_json
        return to_section_json(self, axis=axis, position=position, exclude_basement=exclude_basement)

    def to_path_section_json(
        self,
        path: list[tuple[float, float, float]],
        exclude_basement: bool = True,
    ) -> dict:
        """임의 경로를 따라 단면 경계선을 JSON-serializable dict로 추출한다.

        Args:
            path: ``(x, y, distance)`` 튜플 리스트. 모델 좌표계 기준.
            exclude_basement: True이면 Basement 경계를 제외한다.
        """
        from .exporters import to_path_section_json
        return to_path_section_json(self, path=path, exclude_basement=exclude_basement)

    def to_dict(self, include_raw: bool = False) -> dict:
        """JSON-serializable dict로 변환한다.

        Args:
            include_raw: True이면 lith_block을 리스트로 포함한다.
                대용량 모델에서는 메모리 사용에 주의.
        """
        d: dict = {
            "total_cells": self.total_cells,
            "resolution": self.resolution,
            "extent": self.extent,
            "element_names": self.element_names,
            "lithology_stats": [
                {
                    "id": s.id,
                    "element_name": s.element_name,
                    "cell_count": s.cell_count,
                    "ratio": round(s.ratio, 6),
                }
                for s in self.lithology_stats
            ],
        }
        if include_raw:
            d["lith_block"] = self.lith_block.tolist()
        return d
