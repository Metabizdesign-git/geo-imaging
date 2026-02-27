"""GemPy 연동 계층.

SDK에서 유일하게 gempy를 import하는 모듈이다.
GemPy API 변경 시 이 파일만 수정하면 된다.
"""

import logging

import gempy as gp
import numpy as np
from gempy.core.color_generator import ColorsGenerator
from gempy.core.data import StructuralElement, StructuralFrame, StructuralGroup
from gempy.core.data.orientations import OrientationsTable
from gempy.core.data.surface_points import SurfacePointsTable
from gempy_engine.core.data.stack_relation_type import StackRelationType

from .exceptions import ComputationError
from .orientation import estimate_orientations, pole_to_angles
from .schemas import (
    GeoModelInput,
    LithologyStats,
    ModelResult,
)

logger = logging.getLogger(__name__)

_RELATION_MAP = {
    "erode": StackRelationType.ERODE,
    "onlap": StackRelationType.ONLAP,
    "fault": StackRelationType.FAULT,
    "basement": StackRelationType.BASEMENT,
}


def build_gempy_model(input_data: GeoModelInput):
    """GeoModelInput 스키마로부터 GemPy GeoModel을 생성한다.

    시추공 데이터를 element별 surface points로 변환한 뒤 GemPy에 전달한다.
    """
    color_gen = ColorsGenerator()
    groups_config = input_data.resolve_structural_groups()
    points_by_element = input_data.group_points_by_element()

    # 1) StructuralFrame 구축
    structural_groups = []
    all_element_names: list[str] = []

    for gc in groups_config:
        elements = []
        for elem_name in gc.elements:
            elements.append(
                StructuralElement(
                    name=elem_name,
                    surface_points=SurfacePointsTable.initialize_empty(),
                    orientations=OrientationsTable.initialize_empty(),
                    color=next(color_gen),
                )
            )
            all_element_names.append(elem_name)
        structural_groups.append(
            StructuralGroup(
                name=gc.name,
                elements=elements,
                structural_relation=_RELATION_MAP[gc.relation],
            )
        )

    structural_frame = StructuralFrame(
        structural_groups=structural_groups,
        color_gen=color_gen,
    )

    # 2) GeoModel 생성
    geo_model = gp.create_geomodel(
        project_name=input_data.project_name,
        extent=input_data.extent.to_list(),
        resolution=input_data.resolution.to_list(),
        structural_frame=structural_frame,
    )

    # 3) Surface Points 추가 (시추공 → element별 변환)
    sp_x, sp_y, sp_z, sp_names = [], [], [], []
    for elem_name in all_element_names:
        for x, y, z in points_by_element.get(elem_name, []):
            sp_x.append(x)
            sp_y.append(y)
            sp_z.append(z)
            sp_names.append(elem_name)

    gp.add_surface_points(
        geo_model=geo_model,
        x=sp_x, y=sp_y, z=sp_z,
        elements_names=sp_names,
    )

    # 4) Orientations 추가
    ori_x, ori_y, ori_z, ori_names = [], [], [], []
    ori_values: list[list[float]] = []

    for elem_name in all_element_names:
        explicit = (input_data.orientations or {}).get(elem_name)
        if explicit:
            for ori in explicit:
                ori_x.append(ori.x)
                ori_y.append(ori.y)
                ori_z.append(ori.z)
                ori_names.append(elem_name)
                if ori.azimuth is not None:
                    ori_values.append([ori.azimuth, ori.dip, ori.polarity])
                else:
                    azimuth, dip = pole_to_angles(ori.gx, ori.gy, ori.gz)
                    ori_values.append([azimuth, dip, ori.polarity or 1.0])
        else:
            pts = points_by_element.get(elem_name, [])
            if pts:
                ori = estimate_orientations(elem_name, pts)
                ori_x.append(ori.x)
                ori_y.append(ori.y)
                ori_z.append(ori.z)
                ori_names.append(elem_name)
                ori_values.append([ori.azimuth, ori.dip, ori.polarity])

    gp.add_orientations(
        geo_model=geo_model,
        x=ori_x, y=ori_y, z=ori_z,
        elements_names=ori_names,
        orientation=np.array(ori_values),
    )

    return geo_model


def compute_gempy_model(geo_model) -> None:
    """GemPy 모델을 계산한다.

    Raises:
        ComputationError: GemPy 내부 계산 실패 시
    """
    try:
        gp.compute_model(geo_model)
    except Exception as e:
        raise ComputationError(f"GemPy computation failed: {e}") from e


def extract_result(geo_model, input_data: GeoModelInput) -> ModelResult:
    """계산된 GemPy GeoModel로부터 ModelResult를 추출한다."""
    sol = geo_model.solutions
    raw = sol.raw_arrays

    lith_block = raw.lith_block
    scalar_field = raw.scalar_field_matrix
    total_cells = int(lith_block.shape[0])

    element_names = [
        e.name
        for g in geo_model.structural_frame.structural_groups
        for e in g.elements
    ]
    all_names = element_names + ["Basement"]

    unique, counts = np.unique(lith_block, return_counts=True)
    lithology_stats = []
    for u, c in zip(unique, counts):
        idx = int(u) - 1
        name = all_names[idx] if idx < len(all_names) else f"Unknown({int(u)})"
        lithology_stats.append(
            LithologyStats(
                id=int(u),
                element_name=name,
                cell_count=int(c),
                ratio=float(c / total_cells),
            )
        )

    return ModelResult(
        lith_block=lith_block,
        scalar_field_matrix=scalar_field,
        lithology_stats=lithology_stats,
        total_cells=total_cells,
        resolution=input_data.resolution.to_list(),
        extent=input_data.extent.to_list(),
        element_names=element_names,
    )
