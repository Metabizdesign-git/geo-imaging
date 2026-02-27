"""Surface Points로부터 지층 방위(orientation)를 자동 추정하는 모듈.

포인트 수에 따라 다른 전략을 사용한다:
  - 3개 이상: Delaunay 삼각분할 → 삼각형 중심 orientation + 꼭짓점 면적가중 orientation
  - 2개:     두 점 기울기로 경사 방향 계산 (직교 방향은 수평 가정)
  - 1개:     수평면 가정 (dip=0)
"""

import logging

import numpy as np
from scipy.spatial import Delaunay, QhullError

from .exceptions import OrientationEstimationError
from .schemas import Orientation

logger = logging.getLogger(__name__)

_ZERO_NORM_THRESHOLD = 1e-15    # 이 값 이하는 영벡터로 취급
_DEGENERATE_THRESHOLD = 1e-10   # 이 값 이하는 퇴화 삼각형/거리로 취급


def estimate_orientations(
    element_name: str,
    points: list[tuple[float, float, float]],
) -> list[Orientation]:
    """element의 surface points로부터 orientation을 자동 추정한다.

    3개 이상의 포인트가 있으면 Delaunay 삼각분할을 수행하여
    각 삼각형마다 로컬 orientation을 생성한다.

    Args:
        element_name: 구조 요소 이름 (로깅용)
        points: (x, y, z) 좌표 리스트

    Returns:
        추정된 Orientation 리스트

    Raises:
        OrientationEstimationError: 추정 실패 시
    """
    pts = np.array(points, dtype=float)
    n = len(pts)

    if n == 1:
        logger.warning(
            "Element '%s': 1 point only — assuming horizontal plane (dip=0)",
            element_name,
        )
        return [_make_orientation(pts[0], np.array([0.0, 0.0, 1.0]))]

    if n == 2:
        logger.warning(
            "Element '%s': 2 points only — orientation estimated from gradient",
            element_name,
        )
        center = pts.mean(axis=0)
        normal = _gradient_from_two_points(pts)
        return [_make_orientation(center, normal)]

    # 3개 이상: Delaunay 삼각분할로 로컬 orientation 다수 생성
    try:
        return _orientations_from_delaunay(pts)
    except (ValueError, QhullError, np.linalg.LinAlgError) as e:
        raise OrientationEstimationError(
            f"Failed to estimate orientation for '{element_name}': {e}"
        ) from e


def pole_to_angles(
    gx: float, gy: float, gz: float,
) -> tuple[float, float]:
    """극벡터(pole vector)를 방위각(azimuth)과 경사(dip)로 변환한다.

    입력 벡터를 정규화한 뒤 변환하므로 단위벡터가 아니어도 안전하다.

    Args:
        gx, gy, gz: 극벡터 성분

    Returns:
        (azimuth, dip) — 도(degree) 단위
    """
    norm = np.sqrt(gx * gx + gy * gy + gz * gz)
    if norm < _ZERO_NORM_THRESHOLD:
        return 0.0, 0.0
    gx, gy, gz = gx / norm, gy / norm, gz / norm

    dip = float(np.degrees(np.arccos(np.clip(gz, -1, 1))))

    if abs(gx) < _DEGENERATE_THRESHOLD and abs(gy) < _DEGENERATE_THRESHOLD:
        azimuth = 0.0
    else:
        azimuth = float(np.degrees(np.arctan2(gx, gy)) % 360)

    return azimuth, dip


def _make_orientation(center: np.ndarray, normal: np.ndarray) -> Orientation:
    """중심점과 법선벡터로 Orientation 객체를 생성한다."""
    # 법선이 항상 위를 향하도록 보정
    if normal[2] < 0:
        normal = -normal
    normal = normal / np.linalg.norm(normal)

    azimuth, dip = pole_to_angles(*normal)
    return Orientation(
        x=float(center[0]), y=float(center[1]), z=float(center[2]),
        azimuth=azimuth, dip=dip, polarity=1.0,
    )


def _orientations_from_delaunay(points: np.ndarray) -> list[Orientation]:
    """Delaunay 삼각분할로 삼각형 중심 + 꼭짓점 orientation을 생성한다.

    1) 각 삼각형의 외적 → 삼각형 중심(centroid)에 orientation 배치
    2) 각 꼭짓점에서 인접 삼각형 법선의 면적가중 평균 → 꼭짓점에 orientation 배치
    """
    tri = Delaunay(points[:, :2])  # x, y로 2D 삼각분할
    orientations: list[Orientation] = []

    # 삼각형별 법선과 면적 계산
    face_normals: list[np.ndarray] = []
    face_areas: list[float] = []

    for simplex in tri.simplices:
        p0, p1, p2 = points[simplex]
        normal = np.cross(p1 - p0, p2 - p0)
        mag = np.linalg.norm(normal)

        if mag < _DEGENERATE_THRESHOLD:
            face_normals.append(np.zeros(3))
            face_areas.append(0.0)
            continue

        face_normals.append(normal / mag)
        face_areas.append(mag * 0.5)

        # 삼각형 중심 orientation
        center = (p0 + p1 + p2) / 3.0
        orientations.append(_make_orientation(center, normal))

    # 꼭짓점 orientation: 인접 삼각형 법선의 면적가중 평균
    n_points = len(points)
    vertex_normals = np.zeros((n_points, 3))

    for i, simplex in enumerate(tri.simplices):
        if face_areas[i] < _DEGENERATE_THRESHOLD:
            continue
        for vi in simplex:
            vertex_normals[vi] += face_normals[i] * face_areas[i]

    for vi in range(n_points):
        mag = np.linalg.norm(vertex_normals[vi])
        if mag < _DEGENERATE_THRESHOLD:
            continue
        orientations.append(_make_orientation(points[vi], vertex_normals[vi]))

    if not orientations:
        raise OrientationEstimationError(
            "All Delaunay triangles are degenerate — cannot estimate orientation"
        )
    return orientations


def _gradient_from_two_points(points: np.ndarray) -> np.ndarray:
    """2개 포인트로부터 면의 법선벡터를 추정한다."""
    diff = points[1] - points[0]
    h_dist = np.linalg.norm(diff[:2])

    if h_dist < _DEGENERATE_THRESHOLD:
        return np.array([0.0, 0.0, 1.0])

    perp = np.array([-diff[1], diff[0], 0.0])
    normal = np.cross(diff, perp)
    return normal / np.linalg.norm(normal)
