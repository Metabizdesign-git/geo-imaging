"""모델 결과 내보내기 모듈.

- 단면 경계선 추출 (to_section_json) — 추가 의존성 없음
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from .schemas import ModelResult


def to_section_json(
    result: ModelResult,
    axis: Literal["xz", "yz", "xy"] = "xz",
    position: float | None = None,
) -> dict:
    """ModelResult의 lith_block에서 지층 경계선을 추출한다.

    voxel raw 데이터 대신 **경계선 좌표(polyline)**만 반환한다.
    프론트엔드에서 SVG ``<polyline>``이나 Canvas ``lineTo``로
    가볍게 렌더링할 수 있다.

    Args:
        result: 계산된 ModelResult 객체.
        axis: 단면 방향.
            - ``"xz"``: Y축 기준 수직 단면 (정면도).
            - ``"yz"``: X축 기준 수직 단면 (측면도).
            - ``"xy"``: Z축 기준 수평 단면 (평면도).
        position: 절단 위치 (실제 좌표). 생략 시 중앙값 사용.

    Returns:
        프론트엔드 렌더링용 dict. ``json.dumps()``로 직렬화 가능.

    Raises:
        ValueError: axis가 유효하지 않거나 position이 범위를 벗어날 때.
    """
    nx, ny, nz = result.resolution
    x_min, x_max, y_min, y_max, z_min, z_max = result.extent

    grid_3d = result.lith_block.reshape(nx, ny, nz)

    # ID → element 이름 매핑
    id_to_name: dict[int, str] = {}
    for stat in result.lithology_stats:
        id_to_name[stat.id] = stat.element_name

    # 축별 슬라이스 + 좌표계 설정
    if axis == "xz":
        if position is None:
            position = (y_min + y_max) / 2
        if not y_min <= position <= y_max:
            raise ValueError(f"position {position}이 Y 범위 [{y_min}, {y_max}]를 벗어남")
        idx = int((position - y_min) / (y_max - y_min) * (ny - 1))
        idx = min(idx, ny - 1)
        # slice_2d[col][row] = grid_3d[x_i, idx, z_i]
        # col axis = x, row axis = z
        slice_2d = grid_3d[:, idx, :]  # (nx, nz)
        n_cols, n_rows = nx, nz
        h_min, h_max = x_min, x_max
        v_min, v_max = z_min, z_max
        h_label, v_label = "x", "z"

    elif axis == "yz":
        if position is None:
            position = (x_min + x_max) / 2
        if not x_min <= position <= x_max:
            raise ValueError(f"position {position}이 X 범위 [{x_min}, {x_max}]를 벗어남")
        idx = int((position - x_min) / (x_max - x_min) * (nx - 1))
        idx = min(idx, nx - 1)
        slice_2d = grid_3d[idx, :, :]  # (ny, nz)
        n_cols, n_rows = ny, nz
        h_min, h_max = y_min, y_max
        v_min, v_max = z_min, z_max
        h_label, v_label = "y", "z"

    elif axis == "xy":
        if position is None:
            position = (z_min + z_max) / 2
        if not z_min <= position <= z_max:
            raise ValueError(f"position {position}이 Z 범위 [{z_min}, {z_max}]를 벗어남")
        idx = int((position - z_min) / (z_max - z_min) * (nz - 1))
        idx = min(idx, nz - 1)
        slice_2d = grid_3d[:, :, idx]  # (nx, ny)
        n_cols, n_rows = nx, ny
        h_min, h_max = x_min, x_max
        v_min, v_max = y_min, y_max
        h_label, v_label = "x", "y"

    else:
        raise ValueError(f"axis는 'xz', 'yz', 'xy' 중 하나여야 합니다: {axis!r}")

    # 경계선 추출: 각 열(col)에서 행(row) 방향으로 값이 바뀌는 지점 탐지
    # slice_2d[col, row] 형태
    h_step = (h_max - h_min) / n_cols
    v_step = (v_max - v_min) / n_rows

    # key: (upper_id, lower_id) → list of (h, v) 좌표
    boundary_points: dict[tuple[int, int], list[list[float]]] = {}

    for col in range(n_cols):
        h_coord = round(h_min + (col + 0.5) * h_step, 2)
        for row in range(n_rows - 1):
            upper_id = int(slice_2d[col, row + 1])  # row+1 = 위쪽 (v 값이 큼)
            lower_id = int(slice_2d[col, row])       # row   = 아래쪽 (v 값이 작음)
            if upper_id != lower_id:
                v_coord = round(v_min + (row + 1) * v_step, 2)
                key = (upper_id, lower_id)
                if key not in boundary_points:
                    boundary_points[key] = []
                boundary_points[key].append([h_coord, v_coord])

    # 경계선 목록 구축
    boundaries = []
    for (upper_id, lower_id), points in boundary_points.items():
        points.sort(key=lambda p: p[0])  # h 좌표 기준 정렬

        # v값이 동일한 연속 구간 압축: 첫/끝 점만 유지
        compressed = [points[0]]
        for i in range(1, len(points)):
            if points[i][1] != points[i - 1][1]:
                if compressed[-1] != points[i - 1]:
                    compressed.append(points[i - 1])
                compressed.append(points[i])
            elif i == len(points) - 1:
                compressed.append(points[i])

        boundaries.append({
            "upper": id_to_name.get(upper_id, f"ID({upper_id})"),
            "lower": id_to_name.get(lower_id, f"ID({lower_id})"),
            "points": compressed,
        })

    # layers: element 이름 목록
    layers = []
    seen = set()
    for stat in result.lithology_stats:
        if stat.id not in seen:
            seen.add(stat.id)
            layers.append(stat.element_name)

    return {
        "axis": axis,
        "position": position,
        "h_axis": h_label,
        "v_axis": v_label,
        "h_range": [h_min, h_max],
        "v_range": [v_min, v_max],
        "layers": layers,
        "boundaries": boundaries,
    }
