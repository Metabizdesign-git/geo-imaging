# 단계별 튜토리얼

이 문서는 GemPyGen을 사용하여 3D 지질 모델을 처음부터 끝까지 구성하는 과정을 안내한다. README의 빠른 시작보다 상세하며, 각 단계의 파라미터 선택 기준과 결과 해석 방법을 포함한다.

---

## 사전 요구사항

- Python >= 3.10
- GemPyGen 설치 완료 (`pip install -e .`)
- GemPy >= 2024.0, gempy-engine 설치 완료

---

## 시나리오

100m × 100m × 300m 영역에 4개의 시추공이 있으며, 3개의 지층(Topsoil, Sandstone, Limestone)이 존재한다.

| 시추공 | x | y | Topsoil (z) | Sandstone (z) | Limestone (z) |
|--------|---|---|-------------|---------------|----------------|
| BH-1 | 0 | 0 | -30 | -100 | -200 |
| BH-2 | 100 | 0 | -25 | -120 | -220 |
| BH-3 | 0 | 100 | -35 | -110 | -210 |
| BH-4 | 100 | 100 | -28 | -115 | -215 |

---

## Step 1: Builder 패턴으로 모델 구성

```python
from gempygen import GeoModelBuilder, BoreholeLayer

builder = GeoModelBuilder("tutorial_model")
```

### 공간 범위 설정

```python
builder.set_extent(
    x_min=0,   x_max=100,    # X축 범위 (미터)
    y_min=0,   y_max=100,    # Y축 범위 (미터)
    z_min=-300, z_max=0,     # Z축 범위 (음수=지하, 0=지표면)
)
```

**범위 설정 기준:**
- 모든 시추공 좌표가 범위 내에 포함되어야 한다
- z 범위는 가장 깊은 관측점보다 넉넉하게 설정한다
- 실무에서는 UTM 좌표계를 사용하는 것이 일반적이다

### 격자 해상도 설정

```python
builder.set_resolution(nx=50, ny=50, nz=50)
```

**해상도 선택 가이드:**
- 프로토타이핑: 20~30 (빠른 계산)
- 일반 사용: 50 (기본값, 균형)
- 정밀 결과: 80~100 (느리지만 상세)
- 최대: 200 (각 축당)

> 전체 셀 수 = nx × ny × nz이므로 50×50×50 = 125,000셀, 100×100×100 = 1,000,000셀이다. 해상도를 2배로 올리면 셀 수가 8배 증가한다.

### 시추공 데이터 입력

```python
builder.add_borehole(0, 0, [
    BoreholeLayer(element="Topsoil",   z=-30),
    BoreholeLayer(element="Sandstone", z=-100),
    BoreholeLayer(element="Limestone", z=-200),
])

builder.add_borehole(100, 0, [
    BoreholeLayer(element="Topsoil",   z=-25),
    BoreholeLayer(element="Sandstone", z=-120),
    BoreholeLayer(element="Limestone", z=-220),
])

builder.add_borehole(0, 100, [
    BoreholeLayer(element="Topsoil",   z=-35),
    BoreholeLayer(element="Sandstone", z=-110),
    BoreholeLayer(element="Limestone", z=-210),
])

builder.add_borehole(100, 100, [
    BoreholeLayer(element="Topsoil",   z=-28),
    BoreholeLayer(element="Sandstone", z=-115),
    BoreholeLayer(element="Limestone", z=-215),
])
```

**참고:**
- 각 시추공에서 동일한 element 이름을 사용해야 같은 surface로 인식된다
- 동일 element의 surface points가 3개 이상이면 SVD 평면 피팅으로 정확한 방위를 추정할 수 있다
- 시추공이 많을수록 모델 품질이 향상된다

### 계산 실행

```python
result = builder.build_and_compute()
```

내부적으로 다음 과정이 순차 실행된다:
1. 입력 검증 (Pydantic)
2. 구조 그룹 자동 생성
3. 방위 자동 추정 (SVD)
4. GemPy 모델 생성 및 계산
5. 결과 추출

---

## Step 2: 결과 확인

### 기본 통계

```python
print(f"전체 셀 수: {result.total_cells:,}")
print(f"해상도: {result.resolution}")
print(f"공간 범위: {result.extent}")
print(f"지층 이름: {result.element_names}")

for stat in result.lithology_stats:
    print(f"  {stat.element_name}: {stat.cell_count:,} cells ({stat.ratio:.1%})")
```

### lith_block 3D 변환

`lith_block`은 1D 배열이다. 3D로 변환하여 단면을 확인할 수 있다:

```python
import numpy as np

nx, ny, nz = result.resolution
block_3d = result.lith_block.reshape(nx, ny, nz)

# 특정 깊이의 수평 단면
z_index = nz // 2  # 중간 깊이
horizontal_slice = block_3d[:, :, z_index]
print(f"Z 인덱스 {z_index} 수평 단면:")
print(horizontal_slice)

# 특정 위치의 수직 단면
x_index = nx // 2  # 중간 X
vertical_slice = block_3d[x_index, :, :]
print(f"X 인덱스 {x_index} 수직 단면:")
print(vertical_slice)
```

### 암상 ID 매핑

```python
# ID와 이름의 대응
# ID 1 = element_names[0], ID 2 = element_names[1], ...
# 마지막 ID = Basement (자동 추가)
for i, name in enumerate(result.element_names, start=1):
    print(f"  ID {i} = {name}")
print(f"  ID {len(result.element_names) + 1} = Basement")
```

---

## Step 3: 클래스 기반 입력

Builder 패턴 대신 `GeoModelInput`을 직접 구성할 수도 있다. 결과는 동일하다.

```python
from gempygen import (
    compute_model,
    GeoModelInput, ModelExtent, ModelResolution,
    Borehole, BoreholeLayer,
)

input_data = GeoModelInput(
    project_name="tutorial_model",
    extent=ModelExtent(
        x_min=0, x_max=100,
        y_min=0, y_max=100,
        z_min=-300, z_max=0,
    ),
    resolution=ModelResolution(nx=50, ny=50, nz=50),
    boreholes=[
        Borehole(x=0, y=0, layers=[
            BoreholeLayer(element="Topsoil",   z=-30),
            BoreholeLayer(element="Sandstone", z=-100),
            BoreholeLayer(element="Limestone", z=-200),
        ]),
        Borehole(x=100, y=0, layers=[
            BoreholeLayer(element="Topsoil",   z=-25),
            BoreholeLayer(element="Sandstone", z=-120),
            BoreholeLayer(element="Limestone", z=-220),
        ]),
        Borehole(x=0, y=100, layers=[
            BoreholeLayer(element="Topsoil",   z=-35),
            BoreholeLayer(element="Sandstone", z=-110),
            BoreholeLayer(element="Limestone", z=-210),
        ]),
        Borehole(x=100, y=100, layers=[
            BoreholeLayer(element="Topsoil",   z=-28),
            BoreholeLayer(element="Sandstone", z=-115),
            BoreholeLayer(element="Limestone", z=-215),
        ]),
    ],
)

result = compute_model(input_data)
```

### Builder ↔ GeoModelInput 변환

```python
# Builder → GeoModelInput
input_data = builder.to_input()

# GeoModelInput → Builder
builder = GeoModelBuilder.from_input(input_data)
```

---

## Step 4: Dict/JSON 입력

API 서버나 JSON 파일에서 데이터를 받는 경우:

```python
from gempygen import compute_model, GeoModelInput

data = {
    "project_name": "tutorial_model",
    "extent": {
        "x_min": 0, "x_max": 100,
        "y_min": 0, "y_max": 100,
        "z_min": -300, "z_max": 0,
    },
    "boreholes": [
        {
            "x": 0, "y": 0,
            "layers": [
                {"element": "Topsoil",   "z": -30},
                {"element": "Sandstone", "z": -100},
                {"element": "Limestone", "z": -200},
            ]
        },
        {
            "x": 100, "y": 0,
            "layers": [
                {"element": "Topsoil",   "z": -25},
                {"element": "Sandstone", "z": -120},
                {"element": "Limestone", "z": -220},
            ]
        },
        # ... 나머지 시추공
    ]
}

input_data = GeoModelInput(**data)
result = compute_model(input_data)
```

JSON 문자열에서 직접 파싱:

```python
import json

json_str = json.dumps(data)
input_data = GeoModelInput.model_validate_json(json_str)
```

---

## Step 5: 명시적 방위 설정 (선택)

자동 추정 대신 지질학적 사전 지식을 반영하려면:

### 각도 방식

```python
from gempygen import Orientation

builder.add_orientations("Sandstone", [
    Orientation(
        x=50, y=50, z=-110,       # 방위 측정 위치
        azimuth=90.0,             # 동쪽으로 기울어짐
        dip=15.0,                 # 15도 경사
        polarity=1.0,             # 상향 법선
    ),
])
```

### 극벡터 방식

```python
builder.add_orientations("Limestone", [
    Orientation(
        x=50, y=50, z=-215,
        gx=0.0, gy=0.0, gz=1.0,  # 수평면 (법선이 위를 향함)
    ),
])
```

> 일부 element만 명시적 방위를 제공하고, 나머지는 자동 추정에 맡길 수 있다.

---

## Step 6: 명시적 구조 그룹 설정 (선택)

복잡한 지질 구조(단층, 부정합 등)를 모델링할 때:

```python
builder.set_group(
    name="Sedimentary",
    elements=["Topsoil", "Sandstone", "Limestone"],
    relation="erode",
)
```

다중 그룹 예시:

```python
builder = GeoModelBuilder("complex_model")
builder.set_extent(0, 200, 0, 200, -500, 0)

# 단층 그룹 (먼저 정의)
builder.set_group(
    name="FaultSystem",
    elements=["MainFault"],
    relation="fault",
)

# 퇴적층 그룹
builder.set_group(
    name="Sedimentary",
    elements=["Sandstone", "Limestone"],
    relation="erode",
)

# 기반암 그룹
builder.set_group(
    name="Base",
    elements=["Granite"],
    relation="basement",
)
```

> 구조 그룹의 정의 순서가 지질학적 상하관계에 영향을 줄 수 있다.

---

## Step 7: 시각화

### scripts/visualize.py 사용

2D 단면도와 3D 표면 렌더링을 이미지로 저장한다:

```python
from gempygen import GeoModelBuilder, BoreholeLayer
from gempygen.engine import build_gempy_model, compute_gempy_model
from scripts.visualize import save_2d_sections, save_3d_surfaces

# 모델 구성 (builder.to_input()으로 GeoModelInput 생성)
geo_model = build_gempy_model(builder.to_input())
compute_gempy_model(geo_model)

# 시각화 저장
save_2d_sections(geo_model, "output_2d.png")
save_3d_surfaces(geo_model, "output_3d.png")
```

**필수 패키지:** `pip install matplotlib pyvista gempy-viewer`

### scripts/report.py 사용

입력/출력 요약을 터미널에 출력한다:

```python
from scripts.report import print_input_summary, print_output_summary

print_input_summary(geo_model)   # Surface Points, Orientations, Grid 정보
print_output_summary(geo_model)  # Lithology Block, Scalar Field 정보
```

---

## 전체 코드

```python
from gempygen import GeoModelBuilder, BoreholeLayer

# 1. 모델 구성
result = (
    GeoModelBuilder("tutorial_model")
    .set_extent(0, 100, 0, 100, -300, 0)
    .set_resolution(50, 50, 50)
    .add_borehole(0, 0, [
        BoreholeLayer(element="Topsoil",   z=-30),
        BoreholeLayer(element="Sandstone", z=-100),
        BoreholeLayer(element="Limestone", z=-200),
    ])
    .add_borehole(100, 0, [
        BoreholeLayer(element="Topsoil",   z=-25),
        BoreholeLayer(element="Sandstone", z=-120),
        BoreholeLayer(element="Limestone", z=-220),
    ])
    .add_borehole(0, 100, [
        BoreholeLayer(element="Topsoil",   z=-35),
        BoreholeLayer(element="Sandstone", z=-110),
        BoreholeLayer(element="Limestone", z=-210),
    ])
    .add_borehole(100, 100, [
        BoreholeLayer(element="Topsoil",   z=-28),
        BoreholeLayer(element="Sandstone", z=-115),
        BoreholeLayer(element="Limestone", z=-215),
    ])
    .build_and_compute()
)

# 2. 결과 확인
print(f"전체 셀 수: {result.total_cells:,}")
for stat in result.lithology_stats:
    print(f"  {stat.element_name}: {stat.cell_count:,} cells ({stat.ratio:.1%})")
```
