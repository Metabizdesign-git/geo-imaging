"""Surface Points로부터 지층 방위(orientation)를 자동 추정하는 모듈.

포인트 수에 따라 다른 전략을 사용한다:
  - 3개 이상: SVD 평면 피팅으로 법선벡터 계산
  - 2개:     두 점 기울기로 경사 방향 계산 (직교 방향은 수평 가정)
  - 1개:     수평면 가정 (dip=0)
"""

import logging

import numpy as np

from .exceptions import OrientationEstimationError
from .schemas import Orientation

logger = logging.getLogger(__name__)


def estimate_orientations(
    element_name: str,
    points: list[tuple[float, float, float]],
) -> Orientation:
    """element의 surface points로부터 단일 orientation을 자동 추정한다.

    Args:
        element_name: 구조 요소 이름 (로깅용)
        points: (x, y, z) 좌표 리스트

    Returns:
        추정된 Orientation (centroid 위치)

    Raises:
        OrientationEstimationError: 추정 실패 시
    """
    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[1] for p in points], dtype=float)
    z = np.array([p[2] for p in points], dtype=float)

    try:
        cx, cy, cz, azimuth, dip, polarity = _compute_from_points(x, y, z)
    except Exception as e:
        raise OrientationEstimationError(
            f"Failed to estimate orientation for '{element_name}': {e}"
        ) from e

    n = len(points)
    if n == 1:
        logger.warning(
            "Element '%s': 1 point only — assuming horizontal plane (dip=0)",
            element_name,
        )
    elif n == 2:
        logger.warning(
            "Element '%s': 2 points only — orientation estimated from gradient",
            element_name,
        )

    return Orientation(
        x=cx, y=cy, z=cz,
        azimuth=azimuth, dip=dip, polarity=polarity,
    )


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
    if norm < 1e-15:
        return 0.0, 0.0
    gx, gy, gz = gx / norm, gy / norm, gz / norm

    dip = float(np.degrees(np.arccos(np.clip(gz, -1, 1))))

    if abs(gx) < 1e-10 and abs(gy) < 1e-10:
        azimuth = 0.0
    else:
        azimuth = float(np.degrees(np.arctan2(gx, gy)) % 360)

    return azimuth, dip


def _compute_from_points(
    x: np.ndarray, y: np.ndarray, z: np.ndarray,
) -> tuple[float, float, float, float, float, float]:
    """단일 지층의 포인트들로부터 orientation을 계산한다.

    Returns:
        (center_x, center_y, center_z, azimuth, dip, polarity)
    """
    points = np.column_stack([x, y, z])
    n = len(points)
    center = points.mean(axis=0)

    if n >= 3:
        normal = _fit_plane_normal(points, center)
    elif n == 2:
        normal = _gradient_from_two_points(points)
    else:
        normal = np.array([0.0, 0.0, 1.0])

    # 법선이 항상 위를 향하도록 보정
    if normal[2] < 0:
        normal = -normal
    normal = normal / np.linalg.norm(normal)

    azimuth, dip = pole_to_angles(*normal)

    return float(center[0]), float(center[1]), float(center[2]), azimuth, dip, 1.0


def _fit_plane_normal(points: np.ndarray, center: np.ndarray) -> np.ndarray:
    """3개 이상 포인트에 대해 SVD로 최적 평면을 피팅하고 법선벡터를 반환한다."""
    centered = points - center
    _, _, vh = np.linalg.svd(centered)
    return vh[-1]


def _gradient_from_two_points(points: np.ndarray) -> np.ndarray:
    """2개 포인트로부터 면의 법선벡터를 추정한다."""
    diff = points[1] - points[0]
    h_dist = np.linalg.norm(diff[:2])

    if h_dist < 1e-10:
        return np.array([0.0, 0.0, 1.0])

    perp = np.array([-diff[1], diff[0], 0.0])
    normal = np.cross(diff, perp)
    return normal / np.linalg.norm(normal)
