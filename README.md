# GemPyGen

GemPy 기반 3D 지질 모델링 SDK.

시추공(borehole) 데이터를 입력하면 암상 블록, 스칼라 필드를 계산하여 반환한다.

## 설치

### GitHub에서 설치

```bash
pip install "git+https://github.com/Metabizdesign-git/geo-imaging"
```

### 시각화 포함 설치

```bash
pip install "gempygen[viz] @ git+https://github.com/Metabizdesign-git/geo-imaging"
```

### 개발 환경 설정

```bash
git clone https://github.com/Metabizdesign-git/geo-imaging.git
cd geo-imaging
pip install -e ".[dev,viz]"
```

## 빠른 시작

### Builder 패턴

```python
from gempygen import GeoModelBuilder, BoreholeLayer

result = (
    GeoModelBuilder("simple_model")
    .set_extent(0, 100, 0, 100, -300, 0)
    .set_resolution(50, 50, 50)
    .add_borehole(0, 0, [BoreholeLayer(element="Sandstone", z=-100), BoreholeLayer(element="Limestone", z=-200)])
    .add_borehole(100, 0, [BoreholeLayer(element="Sandstone", z=-120), BoreholeLayer(element="Limestone", z=-220)])
    .add_borehole(0, 100, [BoreholeLayer(element="Sandstone", z=-110), BoreholeLayer(element="Limestone", z=-210)])
    .build_and_compute()
)

print(f"Total cells: {result.total_cells}")
for stat in result.lithology_stats:
    print(f"  {stat.element_name}: {stat.cell_count} cells ({stat.ratio:.1%})")
```

각 시추공은 동일 (x, y) 좌표에서 깊이별 지층을 기술한다:

```python
.add_borehole(x, y, [
    BoreholeLayer(element="지층이름", z=z깊이),
    BoreholeLayer(element="지층이름", z=z깊이),
    ...
])
```

### 클래스 기반 입력

```python
from gempygen import (
    compute_model,
    GeoModelInput, ModelExtent, Borehole, BoreholeLayer,
)

input_data = GeoModelInput(
    project_name="my_model",
    extent=ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0),
    boreholes=[
        Borehole(x=0, y=0, layers=[
            BoreholeLayer(element="Sandstone", z=-100),
            BoreholeLayer(element="Limestone", z=-200),
        ]),
        Borehole(x=100, y=0, layers=[
            BoreholeLayer(element="Sandstone", z=-120),
            BoreholeLayer(element="Limestone", z=-220),
        ]),
        Borehole(x=0, y=100, layers=[
            BoreholeLayer(element="Sandstone", z=-110),
            BoreholeLayer(element="Limestone", z=-210),
        ]),
    ],
)

result = compute_model(input_data)
```

### Dict 입력 (API/JSON 연동)

```python
from gempygen import compute_model, GeoModelInput

data = {
    "project_name": "api_model",
    "extent": {
        "x_min": 0, "x_max": 100,
        "y_min": 0, "y_max": 100,
        "z_min": -300, "z_max": 0
    },
    "boreholes": [
        {
            "x": 0, "y": 0,
            "layers": [
                {"element": "Sandstone", "z": -100},
                {"element": "Limestone", "z": -200}
            ]
        },
        {
            "x": 100, "y": 0,
            "layers": [
                {"element": "Sandstone", "z": -120},
                {"element": "Limestone", "z": -220}
            ]
        },
        {
            "x": 0, "y": 100,
            "layers": [
                {"element": "Sandstone", "z": -110},
                {"element": "Limestone", "z": -210}
            ]
        }
    ]
}

input_data = GeoModelInput(**data)
result = compute_model(input_data)
```

## API 레퍼런스

### 최상위 함수

| 함수 | 설명 | 반환 |
|------|------|------|
| `compute_model(input_data)` | `GeoModelInput`으로부터 지질 모델 계산 | ModelResult |
| `to_section_json(result, axis, position)` | 단면 경계선 추출 (프론트엔드 렌더링용) | dict |

### GeoModelBuilder

| 메서드 | 설명 | 반환 |
|--------|------|------|
| `set_extent(x_min, x_max, y_min, y_max, z_min, z_max)` | 공간 범위 설정 | self |
| `set_resolution(nx, ny, nz)` | 격자 해상도 설정 (기본 50x50x50) | self |
| `add_borehole(x, y, [BoreholeLayer(...), ...])` | 시추공 데이터 추가 | self |
| `set_group(name, elements, relation)` | 구조 그룹 명시 설정 (선택) | self |
| `add_orientations(element, [Orientation(...), ...])` | 명시적 방위 추가 (선택) | self |
| `to_input()` | 검증된 `GeoModelInput` 반환 | GeoModelInput |
| `build_and_compute()` | 모델 생성 + 계산 + 결과 반환 | ModelResult |
| `from_input(GeoModelInput)` | 스키마로부터 빌더 생성 | GeoModelBuilder |

### 입력 스키마

| 클래스 | 설명 |
|--------|------|
| `GeoModelInput` | 최상위 입력 (project_name, extent, resolution, boreholes) |
| `Borehole` | 시추공 (x, y, layers) |
| `BoreholeLayer` | 깊이별 지층 관측 (element, z) |
| `ModelExtent` | 공간 범위 (x/y/z min/max) |
| `ModelResolution` | 격자 해상도 (nx, ny, nz) |
| `StructuralGroupConfig` | 구조 그룹 설정 (선택, 생략 시 자동) |
| `Orientation` | 방위 (선택, 생략 시 SVD 자동 추정) |

### 출력: ModelResult

| 필드 | 타입 | 설명 |
|------|------|------|
| `lith_block` | np.ndarray | 셀별 암상 ID (1D) |
| `scalar_field_matrix` | np.ndarray | 스칼라 필드 (groups x cells) |
| `lithology_stats` | list[LithologyStats] | 암상별 통계 (id, name, cell_count, ratio) |
| `total_cells` | int | 전체 셀 수 |
| `resolution` | list[int] | [nx, ny, nz] |
| `extent` | list[float] | [x_min, x_max, y_min, y_max, z_min, z_max] |
| `element_names` | list[str] | 구조 요소 이름 목록 |

### 예외

```python
from gempygen import GempygenError, ValidationError, ComputationError

try:
    result = builder.build_and_compute()
except ValidationError as e:
    print(f"입력 오류: {e}")
except ComputationError as e:
    print(f"계산 실패: {e}")
except GempygenError as e:
    print(f"SDK 오류: {e}")
```

| 예외 | 상황 |
|------|------|
| `ValidationError` | 입력 데이터 검증 실패 |
| `InsufficientPointsError` | surface points 부족 |
| `ComputationError` | GemPy 계산 엔진 실패 |
| `OrientationEstimationError` | 방위 자동 추정 실패 |

## 자동 추정

### Structural Groups

`set_group()`을 호출하지 않으면 시추공 데이터에서 발견된 모든 element를 단일 `erode` 그룹으로 자동 구성한다.

### Orientation

`add_orientations()`를 호출하지 않으면 각 element의 surface points로부터 SVD 평면 피팅으로 자동 추정한다:

| 포인트 수 | 전략 |
|-----------|------|
| 3개 이상 | SVD 평면 피팅으로 법선벡터 계산 |
| 2개 | 두 점 기울기 기반 추정 |
| 1개 | 수평면 가정 (dip=0) |

## 패키지 구조

```
src/gempygen/
├── __init__.py       # 공개 API export
├── _version.py       # 버전 정보
├── schemas.py        # Pydantic 입출력 스키마
├── builder.py        # GeoModelBuilder (메인 API)
├── engine.py         # GemPy 연동 계층
├── exporters.py      # 단면 경계선 추출
├── orientation.py    # SVD 기반 방위 자동 추정
└── exceptions.py     # 예외 계층
```

## 의존성

- Python >= 3.10
- gempy >= 2024.0
- gempy-engine
- numpy >= 1.24
- pydantic >= 2.0
