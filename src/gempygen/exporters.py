"""모델 결과 내보내기 모듈.

- 단면 경계선 추출 (to_section_json) — 추가 의존성 없음
- 임의 경로 단면 경계선 추출 (to_path_section_json) — scipy, scikit-image 선택 의존
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Literal

import numpy as np

from .exceptions import ValidationError
from .schemas import BASEMENT_ELEMENT_NAME, ModelResult

logger = logging.getLogger(__name__)


def _id_to_name_map(result: ModelResult) -> dict[int, str]:
    """lithology_stats에서 ID → element 이름 매핑을 생성한다."""
    return {s.id: s.element_name for s in result.lithology_stats}


def _layers_list(result: ModelResult, exclude_basement: bool) -> list[str]:
    """element 이름 목록을 반환한다."""
    layers = []
    seen: set[int] = set()
    for stat in result.lithology_stats:
        if stat.id not in seen:
            if exclude_basement and stat.element_name.lower() == BASEMENT_ELEMENT_NAME.lower():
                continue
            seen.add(stat.id)
            layers.append(stat.element_name)
    return layers


def _filter_basement(boundaries: list[dict], exclude_basement: bool) -> list[dict]:
    """Basement 관련 경계선을 필터링한다."""
    if not exclude_basement:
        return boundaries
    return [
        b for b in boundaries
        if b.get("upper_element", "").lower() != BASEMENT_ELEMENT_NAME.lower()
        and b.get("lower_element", "").lower() != BASEMENT_ELEMENT_NAME.lower()
    ]


def _cell_centers(vmin: float, vmax: float, n: int) -> np.ndarray:
    """셀 중심 좌표 배열을 계산한다."""
    d = (vmax - vmin) / n
    return np.linspace(vmin + d / 2, vmax - d / 2, n)


# ── 임의 경로 경계선 추출 (contour / discrete) ────────────────


def _find_contour_levels(
    lith_slice: np.ndarray, scalar_slice: np.ndarray,
) -> list[tuple[float, int, int]]:
    """lith_slice 전이 지점에서 scalar field의 등고선 레벨을 탐지한다."""
    transitions: dict[tuple[int, int], list[float]] = {}
    n_pts, nz = lith_slice.shape
    for i in range(n_pts):
        for j in range(nz - 1):
            lower_id, upper_id = int(lith_slice[i, j]), int(lith_slice[i, j + 1])
            if lower_id != upper_id and lower_id > 0 and upper_id > 0:
                key = (lower_id, upper_id)
                val = (scalar_slice[i, j] + scalar_slice[i, j + 1]) / 2
                transitions.setdefault(key, []).append(val)

    result = []
    for (lower_id, upper_id), vals in sorted(transitions.items()):
        result.append((float(np.median(vals)), lower_id, upper_id))
    return result


def _extract_contour_boundaries(
    lith_slice: np.ndarray,
    scalar_slice: np.ndarray,
    distances: np.ndarray,
    z_values: np.ndarray,
    id_to_name: dict[int, str],
) -> list[dict]:
    """scikit-image find_contours로 부드러운 경계선을 추출한다."""
    from skimage.measure import find_contours

    levels = _find_contour_levels(lith_slice, scalar_slice)
    if not levels:
        return []

    boundaries = []
    for level, lower_id, upper_id in levels:
        contours = find_contours(scalar_slice, level=level)
        for contour in contours:
            points = []
            for row, col in contour:
                d = float(np.interp(row, np.arange(len(distances)), distances))
                z = float(np.interp(col, np.arange(len(z_values)), z_values))
                points.append([round(d, 3), round(z, 3)])
            points.sort(key=lambda p: p[0])
            if len(points) >= 2:
                boundaries.append({
                    "upper_element": id_to_name.get(upper_id, f"lith_{upper_id}"),
                    "lower_element": id_to_name.get(lower_id, f"lith_{lower_id}"),
                    "points": points,
                })
    return boundaries


def _extract_discrete_boundaries(
    lith_slice: np.ndarray,
    distances: np.ndarray,
    z_values: np.ndarray,
    id_to_name: dict[int, str],
    smooth_window: int = 5,
) -> list[dict]:
    """이산 전이 감지 + 스무딩으로 경계선을 추출한다 (폴백)."""
    try:
        from scipy.ndimage import uniform_filter1d
    except ImportError:
        uniform_filter1d = None

    bp: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for i in range(len(distances)):
        for j in range(len(z_values) - 1):
            lower_id, upper_id = int(lith_slice[i, j]), int(lith_slice[i, j + 1])
            if lower_id != upper_id and lower_id > 0 and upper_id > 0:
                z_mid = (z_values[j] + z_values[j + 1]) / 2
                bp[(lower_id, upper_id)].append((distances[i], z_mid))

    boundaries = []
    for (lower_id, upper_id), raw in sorted(bp.items()):
        raw.sort(key=lambda p: p[0])
        d_arr = np.array([p[0] for p in raw])
        z_arr = np.array([p[1] for p in raw])
        if uniform_filter1d is not None and len(z_arr) >= smooth_window:
            z_arr = uniform_filter1d(z_arr, size=smooth_window)
        pts = [[round(float(d), 3), round(float(z), 3)] for d, z in zip(d_arr, z_arr)]
        if len(pts) >= 2:
            boundaries.append({
                "upper_element": id_to_name.get(upper_id, f"lith_{upper_id}"),
                "lower_element": id_to_name.get(lower_id, f"lith_{lower_id}"),
                "points": pts,
            })
    return boundaries


def to_section_json(
    result: ModelResult,
    axis: Literal["xz", "yz", "xy"] = "xz",
    position: float | None = None,
    exclude_basement: bool = True,
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
            raise ValidationError(f"position {position}이 Y 범위 [{y_min}, {y_max}]를 벗어남")
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
            raise ValidationError(f"position {position}이 X 범위 [{x_min}, {x_max}]를 벗어남")
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
            raise ValidationError(f"position {position}이 Z 범위 [{z_min}, {z_max}]를 벗어남")
        idx = int((position - z_min) / (z_max - z_min) * (nz - 1))
        idx = min(idx, nz - 1)
        slice_2d = grid_3d[:, :, idx]  # (nx, ny)
        n_cols, n_rows = nx, ny
        h_min, h_max = x_min, x_max
        v_min, v_max = y_min, y_max
        h_label, v_label = "x", "y"

    else:
        raise ValidationError(f"axis는 'xz', 'yz', 'xy' 중 하나여야 합니다: {axis!r}")

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
        upper_name = id_to_name.get(upper_id, f"ID({upper_id})")
        lower_name = id_to_name.get(lower_id, f"ID({lower_id})")

        if exclude_basement and (
            lower_name.lower() == BASEMENT_ELEMENT_NAME.lower()
            or upper_name.lower() == BASEMENT_ELEMENT_NAME.lower()
        ):
            logger.debug("exclude_basement: %s or %s", lower_name, upper_name)
            continue

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
            "upper": upper_name,
            "lower": lower_name,
            "points": compressed,
        })

    return {
        "axis": axis,
        "position": position,
        "h_axis": h_label,
        "v_axis": v_label,
        "h_range": [h_min, h_max],
        "v_range": [v_min, v_max],
        "layers": _layers_list(result, exclude_basement),
        "boundaries": boundaries,
    }


def to_path_section_json(
    result: ModelResult,
    path: list[tuple[float, float, float]],
    exclude_basement: bool = True,
) -> dict:
    """ModelResult에서 임의 경로를 따라 지층 경계선을 추출한다.

    축 정렬이 아닌 임의의 (x, y) 경로를 따라 수직 단면을 절단하고,
    스칼라 필드 등고선(contour) 기반으로 부드러운 경계선을 추출한다.
    scikit-image가 없으면 이산(discrete) 방식으로 폴백한다.

    Args:
        result: 계산된 ModelResult 객체.
        path: ``(x, y, distance)`` 튜플 리스트. 모델 좌표계 기준.
            distance는 경로를 따른 누적 거리 (경계선 수평축으로 사용).
        exclude_basement: True이면 Basement 경계 제외 (기본 True).

    Returns:
        프론트엔드 렌더링용 dict::

            {
                "h_range": [min_dist, max_dist],
                "v_range": [z_min, z_max],
                "layers": ["layer1", ...],
                "boundaries": [
                    {"upper_element": "...", "lower_element": "...", "points": [[d, z], ...]},
                ],
                "top_element": "...",
            }

    Raises:
        ImportError: scipy가 설치되지 않은 경우.
    """
    try:
        from scipy.interpolate import RegularGridInterpolator
    except ImportError:
        raise ImportError(
            "scipy is required for path section extraction. "
            "Install with: pip install gempygen[section]"
        )

    try:
        import skimage  # noqa: F401
        has_skimage = True
    except ImportError:
        has_skimage = False

    nx, ny, nz = result.resolution
    x_min, x_max, y_min, y_max, z_min, z_max = result.extent

    grid_3d = result.lith_block.reshape(nx, ny, nz)
    scalar_3d = result.scalar_field_matrix[0].reshape(nx, ny, nz)

    x_centers = _cell_centers(x_min, x_max, nx)
    y_centers = _cell_centers(y_min, y_max, ny)
    z_centers = _cell_centers(z_min, z_max, nz)

    lith_interp = RegularGridInterpolator(
        (x_centers, y_centers, z_centers), grid_3d.astype(float),
        method="nearest", bounds_error=False, fill_value=0,
    )
    scalar_interp = RegularGridInterpolator(
        (x_centers, y_centers, z_centers), scalar_3d,
        method="linear", bounds_error=False, fill_value=np.nan,
    )

    distances = []
    lith_columns = []
    scalar_columns = []

    for x, y, dist in path:
        distances.append(dist)
        query = np.column_stack([np.full(nz, x), np.full(nz, y), z_centers])
        lith_columns.append(lith_interp(query))
        scalar_columns.append(scalar_interp(query))

    lith_slice = np.array(lith_columns)       # (n_points, nz)
    scalar_slice = np.array(scalar_columns)   # (n_points, nz)
    dist_arr = np.array(distances)

    id_to_name = _id_to_name_map(result)

    # 경계선 추출: contour 우선, discrete 폴백
    boundaries: list[dict] = []
    method = "discrete"
    if has_skimage:
        try:
            boundaries = _extract_contour_boundaries(
                lith_slice, scalar_slice, dist_arr, z_centers, id_to_name,
            )
            if boundaries:
                method = "contour"
        except Exception as e:
            logger.warning("Contour extraction failed, using discrete fallback", exc_info=True)

    if not boundaries:
        boundaries = _extract_discrete_boundaries(
            lith_slice, dist_arr, z_centers, id_to_name,
        )

    boundaries = _filter_basement(boundaries, exclude_basement)

    # 첫 경로 지점의 최상단 element
    top_lith_id = int(lith_slice[0, -1]) if lith_slice.shape[1] > 0 else 0
    top_element = id_to_name.get(top_lith_id, f"lith_{top_lith_id}")

    return {
        "h_range": [round(float(dist_arr[0]), 3), round(float(dist_arr[-1]), 3)],
        "v_range": [z_min, z_max],
        "layers": _layers_list(result, exclude_basement),
        "boundaries": boundaries,
        "top_element": top_element,
        "method": method,
    }
