# 고급 사용법

GemPyGen을 프로덕션 환경에서 활용하기 위한 통합 패턴, 성능 가이드, 고급 기능을 다룬다.

---

## FastAPI / REST API 연동

GemPyGen의 입력 스키마는 Pydantic 기반이므로 FastAPI와 자연스럽게 통합된다.

```python
from fastapi import FastAPI, HTTPException
from gempygen import compute_model, GeoModelInput, ComputationError

app = FastAPI()

@app.post("/compute")
def compute(input_data: GeoModelInput):
    """GeoModelInput을 request body로 직접 수신하여 계산한다."""
    try:
        result = compute_model(input_data)
    except ComputationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # numpy 배열은 JSON 직렬화 불가 → tolist() 변환
    return {
        "total_cells": result.total_cells,
        "resolution": result.resolution,
        "extent": result.extent,
        "element_names": result.element_names,
        "lith_block": result.lith_block.tolist(),
        "lithology_stats": [
            {
                "id": s.id,
                "element_name": s.element_name,
                "cell_count": s.cell_count,
                "ratio": s.ratio,
            }
            for s in result.lithology_stats
        ],
    }
```

> `ModelResult`에는 `np.ndarray` 필드가 포함되어 있으므로, JSON 응답 시 `tolist()` 변환이 필요하다.

---

## CSV 시추공 데이터 가져오기

실무에서는 시추공 데이터가 CSV나 엑셀 파일로 제공되는 경우가 많다.

### CSV 형식 예시

```csv
borehole_id,x,y,element,z
BH-1,0,0,Topsoil,-30
BH-1,0,0,Sandstone,-100
BH-1,0,0,Limestone,-200
BH-2,100,0,Topsoil,-25
BH-2,100,0,Sandstone,-120
BH-2,100,0,Limestone,-220
```

### pandas로 변환

```python
import pandas as pd
from gempygen import GeoModelBuilder, BoreholeLayer

df = pd.read_csv("boreholes.csv")

builder = GeoModelBuilder("from_csv")
builder.set_extent(
    x_min=df["x"].min() - 10,
    x_max=df["x"].max() + 10,
    y_min=df["y"].min() - 10,
    y_max=df["y"].max() + 10,
    z_min=df["z"].min() - 50,
    z_max=0,
)

for bh_id, group in df.groupby("borehole_id"):
    row = group.iloc[0]
    layers = [
        BoreholeLayer(element=r["element"], z=r["z"])
        for _, r in group.iterrows()
    ]
    builder.add_borehole(row["x"], row["y"], layers)

result = builder.build_and_compute()
```

---

## 대규모 모델 처리

### 해상도와 성능

| 해상도 | 셀 수 | 메모리 (lith_block) | 용도 |
|--------|--------|---------------------|------|
| 20×20×20 | 8,000 | ~64 KB | 빠른 프로토타이핑 |
| 50×50×50 | 125,000 | ~1 MB | 일반 사용 (기본값) |
| 100×100×100 | 1,000,000 | ~8 MB | 정밀 분석 |
| 200×200×200 | 8,000,000 | ~64 MB | 최대 (축당 상한) |

`scalar_field_matrix`는 `(그룹 수 × 셀 수) × 8바이트`의 메모리를 추가로 사용한다.

### 프로토타이핑 워크플로우

```python
# 1. 낮은 해상도로 빠르게 검증
result_draft = (
    GeoModelBuilder("test")
    .set_extent(0, 100, 0, 100, -300, 0)
    .set_resolution(20, 20, 20)  # 빠른 계산
    .add_borehole(...)
    .build_and_compute()
)
# → 결과 확인, 입력 데이터 보정

# 2. 최종 해상도로 계산
result_final = (
    GeoModelBuilder("final")
    .set_extent(0, 100, 0, 100, -300, 0)
    .set_resolution(100, 100, 100)  # 정밀 결과
    .add_borehole(...)
    .build_and_compute()
)
```

---

## 다중 구조 그룹 시나리오

### 단층 포함 모델

```python
builder = GeoModelBuilder("fault_model")
builder.set_extent(0, 200, 0, 200, -500, 0)

# 단층 그룹 (먼저 정의)
builder.set_group("FaultSystem", ["MainFault"], relation="fault")

# 퇴적층 그룹
builder.set_group("Sedimentary", ["Sandstone", "Limestone"], relation="erode")

# 기반암 그룹
builder.set_group("Base", ["Granite"], relation="basement")

# 단층 데이터 추가
builder.add_borehole(100, 100, [
    BoreholeLayer(element="MainFault", z=-150),
    BoreholeLayer(element="Sandstone", z=-200),
    BoreholeLayer(element="Limestone", z=-350),
    BoreholeLayer(element="Granite",   z=-450),
])
# ... 추가 시추공
```

### erode + onlap 혼합

```python
# 하부 퇴적층 (침식 관계)
builder.set_group("Lower", ["Shale", "Mudstone"], relation="erode")

# 상부 퇴적층 (부정합 관계 — 기존 지형 위에 퇴적)
builder.set_group("Upper", ["Sandstone", "Siltstone"], relation="onlap")
```

---

## 방위 자동 추정의 한계

### SVD 평면 피팅

3개 이상의 포인트에 대해 SVD(특이값 분해)로 최적 평면을 피팅한다. 공분산 행렬의 최소 고유값에 대응하는 고유벡터가 법선벡터가 된다.

**정확한 경우:**
- 포인트가 넓게 분포된 경우
- 실제 지층이 비교적 평면에 가까운 경우

**부정확할 수 있는 경우:**
- 포인트가 거의 일직선상에 있는 경우 (면을 특정하기 어려움)
- 실제 지층이 강하게 곡면인 경우 (평면 근사의 한계)
- 포인트 수가 2개 이하인 경우

### 하이브리드 접근

정확도가 중요한 element만 수동 방위를 제공하고, 나머지는 자동 추정에 맡길 수 있다:

```python
# Sandstone만 명시적 방위 제공
builder.add_orientations("Sandstone", [
    Orientation(x=50, y=50, z=-110, azimuth=90, dip=15, polarity=1),
])

# Topsoil, Limestone은 자동 추정
result = builder.build_and_compute()
```

---

## Orientation의 두 가지 표현

### 각도 표현 → 지질학자 친화적

```python
Orientation(x=50, y=50, z=-100, azimuth=90, dip=30, polarity=1)
```

### 극벡터 표현 → 프로그래밍 친화적

```python
Orientation(x=50, y=50, z=-100, gx=0.5, gy=0.0, gz=0.866)
```

### 변환

```python
from gempygen.orientation import pole_to_angles

azimuth, dip = pole_to_angles(gx=0.5, gy=0.0, gz=0.866)
print(f"azimuth={azimuth:.1f}°, dip={dip:.1f}°")
```

---

## Builder vs 함수형 API 선택 기준

| 기준 | Builder 패턴 | `compute_model()` |
|------|-------------|-------------------|
| 사용 시나리오 | 대화형 구성, 점진적 데이터 추가 | 일괄 처리, API 요청 처리 |
| 코드 스타일 | 메서드 체이닝 | 단일 함수 호출 |
| 입력 형태 | 개별 메서드 호출 | `GeoModelInput` 객체 |
| 유연성 | 조건부 데이터 추가 용이 | 완성된 입력 데이터 필요 |

```python
# Builder: 조건부 구성이 자연스러움
builder = GeoModelBuilder("model")
builder.set_extent(...)
for bh in borehole_list:
    builder.add_borehole(bh.x, bh.y, bh.layers)
if has_orientation_data:
    builder.add_orientations(...)
result = builder.build_and_compute()

# 함수형: 완성된 데이터를 한 번에 전달
input_data = GeoModelInput(**request_body)
result = compute_model(input_data)
```

---

## GeoModelInput 유틸리티 메서드

`GeoModelInput`은 시추공 데이터를 분석하는 3개의 공개 메서드를 제공한다. 계산 전에 입력 데이터를 검사하거나 디버깅할 때 유용하다.

### discover_elements()

시추공 데이터에서 element 이름을 **등장 순서대로** 추출한다. 이 순서가 결과의 암상 ID 매핑을 결정한다.

```python
input_data = builder.to_input()
elements = input_data.discover_elements()
print(elements)  # ['Topsoil', 'Sandstone', 'Limestone']
```

### group_points_by_element()

시추공 데이터를 element별 `(x, y, z)` 좌표 리스트로 변환한다. 각 element에 몇 개의 surface point가 있는지 확인할 수 있다.

```python
points = input_data.group_points_by_element()
for name, pts in points.items():
    print(f"  {name}: {len(pts)}개 포인트")
# Topsoil: 4개 포인트
# Sandstone: 4개 포인트
# Limestone: 4개 포인트
```

### resolve_structural_groups()

`structural_groups`가 명시되지 않은 경우 자동 생성된 기본 그룹을 확인한다.

```python
groups = input_data.resolve_structural_groups()
for g in groups:
    print(f"  {g.name} ({g.relation}): {g.elements}")
# Default (erode): ['Topsoil', 'Sandstone', 'Limestone']
```

---

## 로깅 활성화

GemPyGen은 Python 표준 `logging` 모듈을 사용한다.

```python
import logging

# SDK 전체 로깅
logging.basicConfig(level=logging.DEBUG)

# 특정 모듈만 활성화
logging.getLogger("gempygen.orientation").setLevel(logging.WARNING)
logging.getLogger("gempygen.engine").setLevel(logging.DEBUG)
```

`gempygen.orientation` 로거는 포인트 수에 따른 추정 전략 경고를 출력한다:
- `"Element 'X': 1 point only — assuming horizontal plane (dip=0)"`
- `"Element 'X': 2 points only — orientation estimated from gradient"`
