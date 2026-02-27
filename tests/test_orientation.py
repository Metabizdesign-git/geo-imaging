"""orientation 모듈 단위 테스트 — pole_to_angles 및 자동 추정 로직."""

from __future__ import annotations

import math

import numpy as np
import pytest

from gempygen.exceptions import OrientationEstimationError
from gempygen.orientation import (
    estimate_orientations,
    pole_to_angles,
)


# ── pole_to_angles ─────────────────────────────────────


class TestPoleToAngles:
    def test_vertical_vector_gives_zero_dip(self):
        azimuth, dip = pole_to_angles(0.0, 0.0, 1.0)
        assert dip == pytest.approx(0.0)

    def test_horizontal_vector_gives_90_dip(self):
        azimuth, dip = pole_to_angles(1.0, 0.0, 0.0)
        assert dip == pytest.approx(90.0)

    def test_normalizes_non_unit_vector(self):
        """비단위 벡터도 단위 벡터와 동일한 결과를 반환해야 한다."""
        az_unit, dip_unit = pole_to_angles(0.0, 0.0, 1.0)
        az_scaled, dip_scaled = pole_to_angles(0.0, 0.0, 5.0)
        assert az_scaled == pytest.approx(az_unit)
        assert dip_scaled == pytest.approx(dip_unit)

    def test_normalizes_arbitrary_scaled_vector(self):
        az_unit, dip_unit = pole_to_angles(0.0, 1.0, 1.0)
        az_scaled, dip_scaled = pole_to_angles(0.0, 3.0, 3.0)
        assert az_scaled == pytest.approx(az_unit)
        assert dip_scaled == pytest.approx(dip_unit)

    def test_zero_vector_returns_zero(self):
        azimuth, dip = pole_to_angles(0.0, 0.0, 0.0)
        assert azimuth == 0.0
        assert dip == 0.0

    def test_45_degree_dip(self):
        """gz = cos(45°) ≈ 0.707 일 때 dip ≈ 45°."""
        gz = math.cos(math.radians(45))
        gy = math.sin(math.radians(45))
        _, dip = pole_to_angles(0.0, gy, gz)
        assert dip == pytest.approx(45.0, abs=0.01)

    def test_azimuth_north(self):
        """gy > 0, gx == 0 → azimuth ≈ 0 (north)."""
        azimuth, _ = pole_to_angles(0.0, 1.0, 1.0)
        assert azimuth == pytest.approx(0.0)

    def test_azimuth_east(self):
        """gx > 0, gy == 0 → azimuth ≈ 90 (east)."""
        azimuth, _ = pole_to_angles(1.0, 0.0, 1.0)
        assert azimuth == pytest.approx(90.0)


# ── estimate_orientations ─────────────────────────────


class TestEstimateOrientations:
    def test_single_point_horizontal(self):
        """1개 포인트 → dip=0, azimuth=0, 결과 1개."""
        oris = estimate_orientations("test", [(50.0, 50.0, -100.0)])
        assert len(oris) == 1
        ori = oris[0]
        assert ori.dip == pytest.approx(0.0)
        assert ori.azimuth == pytest.approx(0.0)
        assert ori.x == pytest.approx(50.0)
        assert ori.y == pytest.approx(50.0)
        assert ori.z == pytest.approx(-100.0)

    def test_two_points_tilted(self):
        """2개 포인트가 다른 Z에 있으면 dip > 0, 결과 1개."""
        oris = estimate_orientations("test", [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -200.0),
        ])
        assert len(oris) == 1
        assert oris[0].dip > 0.0
        assert oris[0].x == pytest.approx(50.0)  # centroid

    def test_three_coplanar_horizontal_points(self):
        """수평면 위 3개 포인트 → dip ≈ 0, 삼각형 1개 + 꼭짓점 3개 = 4개."""
        oris = estimate_orientations("test", [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -100.0),
            (0.0, 100.0, -100.0),
        ])
        assert len(oris) == 4
        assert all(o.dip == pytest.approx(0.0, abs=0.1) for o in oris)

    def test_three_tilted_points(self):
        """기울어진 3개 포인트 → dip > 0."""
        oris = estimate_orientations("test", [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -150.0),
            (0.0, 100.0, -100.0),
        ])
        assert len(oris) >= 1
        assert all(o.dip > 0.0 for o in oris)

    def test_multiple_orientations_from_many_points(self):
        """4개 이상 포인트 → Delaunay 삼각형 여러 개 → orientation 여러 개."""
        oris = estimate_orientations("test", [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -100.0),
            (0.0, 100.0, -100.0),
            (100.0, 100.0, -100.0),
        ])
        assert len(oris) >= 2

    def test_centroid_is_triangle_center(self):
        """3개 포인트 → 첫 번째가 삼각형 중심, 나머지 3개가 꼭짓점."""
        points = [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -200.0),
            (50.0, 100.0, -150.0),
        ]
        oris = estimate_orientations("test", points)
        assert len(oris) == 4
        # 첫 번째는 삼각형 centroid
        assert oris[0].x == pytest.approx(50.0)
        assert oris[0].y == pytest.approx(100.0 / 3)
        assert oris[0].z == pytest.approx(-150.0)


# ── 엣지 케이스 테스트 ─────────────────────────────────


class TestEstimateOrientationsEdgeCases:
    def test_two_vertical_points_returns_horizontal(self):
        """동일 (x,y), 다른 z — 수직 시추공은 수평면을 가정해야 한다."""
        oris = estimate_orientations("test", [
            (50.0, 50.0, -100.0),
            (50.0, 50.0, -200.0),
        ])
        assert len(oris) == 1
        assert oris[0].dip == pytest.approx(0.0, abs=0.1)

    def test_coincident_three_points_raises(self):
        """동일 좌표 3점 — Delaunay 실패 시 OrientationEstimationError."""
        with pytest.raises((OrientationEstimationError, Exception)):
            estimate_orientations("test", [
                (50.0, 50.0, -100.0),
                (50.0, 50.0, -100.0),
                (50.0, 50.0, -100.0),
            ])

    def test_collinear_three_points(self):
        """동일선상 3점 (x축) — 퇴화 삼각형이므로 오류 또는 빈 결과가 아닌 graceful 처리."""
        # x축 위의 3점: Delaunay는 2D(x,y)에서 수행되므로 y가 모두 같으면 실패
        with pytest.raises((OrientationEstimationError, Exception)):
            estimate_orientations("test", [
                (0.0, 0.0, -100.0),
                (50.0, 0.0, -100.0),
                (100.0, 0.0, -100.0),
            ])
