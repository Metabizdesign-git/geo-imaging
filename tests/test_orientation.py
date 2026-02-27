"""orientation 모듈 단위 테스트 — pole_to_angles 및 자동 추정 로직."""

from __future__ import annotations

import math

import numpy as np
import pytest

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
        """1개 포인트 → dip=0, azimuth=0."""
        ori = estimate_orientations("test", [(50.0, 50.0, -100.0)])
        assert ori.dip == pytest.approx(0.0)
        assert ori.azimuth == pytest.approx(0.0)
        assert ori.x == pytest.approx(50.0)
        assert ori.y == pytest.approx(50.0)
        assert ori.z == pytest.approx(-100.0)

    def test_two_points_tilted(self):
        """2개 포인트가 다른 Z에 있으면 dip > 0."""
        ori = estimate_orientations("test", [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -200.0),
        ])
        assert ori.dip > 0.0
        assert ori.x == pytest.approx(50.0)  # centroid

    def test_three_coplanar_horizontal_points(self):
        """수평면 위 3개 포인트 → dip ≈ 0."""
        ori = estimate_orientations("test", [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -100.0),
            (0.0, 100.0, -100.0),
        ])
        assert ori.dip == pytest.approx(0.0, abs=0.1)

    def test_three_tilted_points(self):
        """기울어진 3개 포인트 → dip > 0."""
        ori = estimate_orientations("test", [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -150.0),
            (0.0, 100.0, -100.0),
        ])
        assert ori.dip > 0.0

    def test_centroid_is_mean(self):
        """반환된 위치가 입력 포인트들의 centroid인지 확인."""
        points = [
            (0.0, 0.0, -100.0),
            (100.0, 0.0, -200.0),
            (50.0, 100.0, -150.0),
        ]
        ori = estimate_orientations("test", points)
        assert ori.x == pytest.approx(50.0)
        assert ori.y == pytest.approx(100.0 / 3)
        assert ori.z == pytest.approx(-150.0)
