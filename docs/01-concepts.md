# 지질 모델링 개념 가이드

GemPyGen SDK를 이해하기 위한 지질학적·수학적 배경지식을 정리한다. 지질학 전공자가 아닌 소프트웨어 개발자를 주요 독자로 상정한다.

---

## 3D 지질 모델이란?

지하 공간을 3차원 격자(voxel grid)로 분할하고, 각 셀에 **암상(lithology) ID**를 할당한 이산적 표현이다.

```
┌────────────────────────────┐
│  nx × ny × nz 격자         │
│  각 셀 → 암상 ID (정수)      │
│  예: 1=Sandstone, 2=Limestone│
└────────────────────────────┘
```

GemPyGen에서는 `ModelResult.lith_block`이 이 격자를 1차원 배열로 평탄화한 결과이다.

---

## 핵심 용어

### 시추공 (Borehole)

지표면에서 수직으로 뚫은 관측 구멍이다. 동일한 (x, y) 좌표에서 깊이(z)별로 관측된 암석 종류를 기록한다.

```
지표면 (z=0)
│
├── z=-50   Topsoil
├── z=-100  Sandstone    ← BoreholeLayer(element="Sandstone", z=-100)
├── z=-200  Limestone    ← BoreholeLayer(element="Limestone", z=-200)
│
▼ 깊이 증가 (z 감소)
```

GemPyGen에서 `BoreholeLayer`의 `z` 값은 해당 지층이 관측된 깊이를 의미한다.

### 지층 (Layer / Element)

동일한 암석 특성을 가진 지질학적 단위이다. GemPyGen에서는 `element`라는 이름으로 참조하며, 시추공 데이터에서 문자열(예: `"Sandstone"`)로 식별한다.

### Surface Points

시추공 데이터에서 추출된 특정 지층의 3D 좌표점이다. 여러 시추공에서 동일한 element를 관측하면, 그 관측점들을 모아 하나의 **지질 표면(surface)**을 정의할 수 있다.

```
시추공 A (0, 0)         시추공 B (100, 0)        시추공 C (0, 100)
  Sandstone z=-100        Sandstone z=-120          Sandstone z=-110
      ●─────────────────────●──────────────────────────●
          → Sandstone surface를 정의하는 3개의 surface points
```

GemPyGen은 시추공 데이터를 자동으로 element별 surface points로 변환한다 (`GeoModelInput.group_points_by_element()`).

---

## 방위 (Orientation)

지질 표면의 기울기와 방향을 기술하는 벡터이다. 3D 공간에서 면이 어느 방향으로 얼마나 기울어져 있는지를 나타낸다.

### 각도 표현 (azimuth, dip, polarity)

| 매개변수 | 설명 | 범위 |
|---------|------|------|
| **azimuth** (방위각) | 경사 방향의 수평 각도. 북쪽=0도, 시계 방향 증가 | 0 ~ 360도 |
| **dip** (경사) | 수평면으로부터의 기울기. 수평=0도, 수직=90도 | 0 ~ 90도 |
| **polarity** (극성) | 법선벡터의 방향 부호 | +1 또는 -1 |

```
        N (0°)
        │
  W ────┼──── E
(270°)  │  (90°)
        S (180°)

azimuth = 90° → 동쪽으로 기울어짐
dip = 30°     → 30도 경사
```

### 극벡터 표현 (gx, gy, gz)

면에 수직인 단위벡터(법선벡터)의 성분이다. 프로그래밍과 수학적 처리에 적합하다.

- `(0, 0, 1)` → 수평면 (dip=0)
- `(1, 0, 0)` → 수직면, 동쪽을 향하는 법선

두 표현은 `pole_to_angles(gx, gy, gz)` 함수로 상호 변환할 수 있다.

### 자동 추정

GemPyGen은 방위를 명시하지 않으면 surface points로부터 자동 추정한다:

| 포인트 수 | 전략 | 정확도 |
|-----------|------|--------|
| 3개 이상 | SVD 평면 피팅으로 법선벡터 계산 | 높음 |
| 2개 | 두 점 기울기 기반 추정 | 중간 |
| 1개 | 수평면 가정 (dip=0) | 낮음 (가정에 의존) |

---

## 구조 그룹 (Structural Group)

동일한 **지질학적 관계**로 묶인 element들의 집합이다. 지층 간의 상호작용 방식을 정의한다.

### 관계 유형

| 유형 | 설명 | 예시 |
|------|------|------|
| **erode** | 상위 지층이 하위 지층을 침식. 가장 일반적 | 퇴적층 간 관계 |
| **onlap** | 지층이 기존 지형 위에 퇴적 (기존 형태 보존) | 부정합 퇴적 |
| **fault** | 단층 — 지층의 불연속적 변위 | 지진 활동에 의한 단층 |
| **basement** | 모델의 최하부 기반암 | 화강암 기반 |

### 기본 동작

`set_group()`을 호출하지 않으면 모든 element가 **단일 erode 그룹**으로 자동 구성된다. 대부분의 단순한 퇴적층 모델에서는 이 기본값으로 충분하다.

```
기본 자동 구성:
  Default 그룹 (erode)
    ├── Sandstone
    ├── Limestone
    └── Shale

명시적 다중 그룹:
  Fault 그룹 (fault)
    └── MainFault
  Sedimentary 그룹 (erode)
    ├── Sandstone
    └── Limestone
  Basement 그룹 (basement)
    └── Granite
```

---

## 스칼라 필드 (Scalar Field)

공간의 각 점에 연속적인 실수값을 할당하는 함수이다. GemPy는 surface points와 orientations를 기반으로 보간을 수행하여 스칼라 필드를 생성한다.

스칼라 필드의 **등치면(isosurface)**이 지질 경계를 정의한다. 즉, 스칼라 값이 특정 임곗값과 같은 면이 두 지층 사이의 경계가 된다.

```
스칼라 값 분포:

  0.2  0.4  0.6  0.8  1.0
  ●────●────●────●────●     ← 등치면 (값=0.5)이 경계
       Sandstone  │  Limestone
```

`ModelResult.scalar_field_matrix`는 `(구조 그룹 수 × 셀 수)` 차원의 행렬이다.

---

## GemPy 보간 원리

GemPy는 **공분산 기반 보간(Co-Kriging)** 방법을 사용한다.

1. **입력**: surface points(위치 데이터)와 orientations(기울기 데이터)
2. **보간**: 두 데이터를 결합하여 공간 전체에 연속적인 스칼라 필드를 생성
3. **경계 결정**: 스칼라 필드의 등치면으로 지질 경계를 정의
4. **이산화**: 각 격자 셀에 해당하는 암상 ID를 할당

이 과정은 GemPyGen에서 `engine.py`가 담당하며, 사용자는 시추공 데이터만 입력하면 된다.
