# 아키텍처 심층 분석

GemPyGen SDK의 내부 설계 결정, 모듈 구조, 데이터 흐름을 설명한다. 기여자와 고급 사용자를 대상으로 한다.

---

## 설계 원칙

### 1. GemPy 격리

`engine.py`만 `gempy`를 import한다. GemPy API가 변경되면 이 파일만 수정하면 되므로 나머지 SDK 코드에 대한 영향이 최소화된다.

```
builder.py  ─→  engine.py  ─→  gempy (외부)
                    ↑
schemas.py ─────────┘
orientation.py ─────┘
```

이 격리 덕분에 `schemas.py`, `builder.py`, `orientation.py`의 단위 테스트는 GemPy 없이도 실행할 수 있다.

### 2. Pydantic 계약

모든 입출력을 Pydantic 모델로 엄격하게 정의한다. 입력 검증이 `to_input()` 시점에 자동 수행되므로, engine에 도달하는 데이터는 항상 유효하다.

### 3. 관심사 분리

| 모듈 | 책임 |
|------|------|
| `schemas.py` | 데이터 구조 정의 + 검증 |
| `builder.py` | 사용자 인터페이스 (Builder 패턴) |
| `engine.py` | GemPy 연동 (변환 + 계산 + 추출) |
| `exporters.py` | 단면 경계선 추출 |
| `orientation.py` | 수학적 방위 추정 |
| `exceptions.py` | 예외 계층 |

---

## 모듈 의존성 그래프

```
┌──────────────┐
│  __init__.py │  ← 공개 API export (모든 모듈 import)
└──────┬───────┘
       │
┌──────▼───────┐     ┌─────────────────┐
│  builder.py  │────→│   engine.py     │────→ gempy (외부)
│              │     │                 │────→ gempy_engine (외부)
│              │     │                 │
│              │     │   ┌─────────────┤
│              │     │   │orientation.py│
└──────┬───────┘     └───┴─────────────┘
       │                       │
       │              ┌───────▼────────┐
       └─────────────→│  schemas.py    │
                      ┌───────┴────────┐
                      │                │
              ┌───────▼────────┐ ┌─────▼──────────┐
              │ exceptions.py  │ │ exporters.py   │
              └────────────────┘ └────────────────┘
```

**핵심 규칙:** 순환 참조가 없다. 의존성은 항상 단방향이다.

---

## 데이터 흐름 상세

```
사용자 입력
  │
  ├─ Builder: GeoModelBuilder().set_extent().add_borehole()...
  │                    │
  │                    ▼
  │              to_input()
  │                    │
  └─ 직접: GeoModelInput(...)
                       │
                       ▼
              ┌─ GeoModelInput ─┐  (Pydantic 검증 완료)
              │                 │
              ▼                 ▼
    resolve_structural      group_points
    _groups()               _by_element()
              │                 │
              ▼                 ▼
         StructuralFrame    Surface Points
         구축                 + Orientations
              │                 │
              └────────┬────────┘
                       ▼
              gp.create_geomodel()
              gp.add_surface_points()
              gp.add_orientations()
                       │
                       ▼
              gp.compute_model()    ← ComputationError 래핑
                       │
                       ▼
              extract_result()
                       │
                       ▼
                 ModelResult
```

---

## schemas.py 설계

### 입력 스키마 계층

```
GeoModelInput
├── project_name: str
├── extent: ModelExtent
│     ├── x_min, x_max (x_min < x_max 검증)
│     ├── y_min, y_max
│     └── z_min, z_max
├── resolution: ModelResolution
│     ├── nx (1~200, 기본 50)
│     ├── ny (1~200, 기본 50)
│     └── nz (1~200, 기본 50)
├── boreholes: list[Borehole]  (최소 1개)
│     ├── x, y: float
│     └── layers: list[BoreholeLayer]  (최소 1개)
│           ├── element: str  (최소 1글자)
│           └── z: float
├── structural_groups: Optional[list[StructuralGroupConfig]]
│     ├── name: str
│     ├── elements: list[str]
│     └── relation: "erode" | "onlap" | "fault" | "basement"
└── orientations: Optional[dict[str, list[Orientation]]]
      ├── x, y, z: float
      └── (azimuth, dip, polarity) 또는 (gx, gy, gz)
```

### model_validator 활용 패턴

- **ModelExtent**: `min < max` 제약. 잘못된 범위는 즉시 오류.
- **ModelResolution**: `gt=0, le=200`으로 Field 수준에서 제약.
- **Orientation**: `_check_orientation_data`에서 각도 또는 극벡터 중 하나가 완전한지 검증.

### discover_elements() — 순서 보존

시추공 데이터에서 element를 **등장 순서대로** 추출한다. 이 순서가 GemPy의 StructuralElement 순서를 결정하며, 결과의 암상 ID 매핑에 영향을 준다.

```python
# 첫 시추공의 layers 순서가 기본 element 순서를 결정
boreholes[0].layers = [
    BoreholeLayer(element="Sandstone", z=-100),  # → ID 1
    BoreholeLayer(element="Limestone", z=-200),  # → ID 2
]
```

### 출력 스키마: arbitrary_types_allowed

`ModelResult`는 `np.ndarray` 필드를 포함한다. Pydantic은 기본적으로 임의 타입을 허용하지 않으므로 `model_config = {"arbitrary_types_allowed": True}`를 설정한다.

---

## builder.py 설계

### Builder 패턴 선택 이유

1. **점진적 데이터 구성**: 시추공을 하나씩 추가하는 워크플로우에 적합
2. **메서드 체이닝**: `builder.set_extent().add_borehole().build_and_compute()` 가독성
3. **불완전 상태 허용**: 중간 상태에서 검증하지 않고, `to_input()`에서 일괄 검증

### 내부 상태 관리

```python
class GeoModelBuilder:
    _project_name: str
    _extent: Optional[ModelExtent]          # None이면 to_input()에서 오류
    _resolution: ModelResolution            # 기본값 50×50×50
    _boreholes: list[Borehole]              # 빈 리스트이면 to_input()에서 오류
    _structural_groups: Optional[list]      # None이면 자동 생성
    _orientations: dict[str, list]          # 빈 dict이면 자동 추정
```

### from_input() — 역방향 변환

`GeoModelInput` → `GeoModelBuilder`로 변환하여, 기존 입력에 추가 데이터를 붙이거나 수정할 수 있다. 이를 통해 두 API 스타일 간의 양방향 호환성을 보장한다.

### compute_model() — 함수형 래퍼

```python
def compute_model(input_data: GeoModelInput) -> ModelResult:
    return GeoModelBuilder.from_input(input_data).build_and_compute()
```

내부적으로 Builder를 생성하여 사용하므로, 코드 경로가 하나로 통일된다.

---

## engine.py 설계

### 격리 계층의 역할

SDK에서 유일하게 `gempy`를 import하는 모듈이다. 세 가지 함수로 GemPy와의 인터페이스를 캡슐화한다:

| 함수 | 역할 |
|------|------|
| `build_gempy_model()` | GeoModelInput → GemPy GeoModel 변환 |
| `compute_gempy_model()` | GemPy 계산 실행 + 예외 래핑 |
| `extract_result()` | GemPy solutions → ModelResult 추출 |

### _RELATION_MAP

문자열 관계 유형을 GemPy의 `StackRelationType` 열거형으로 매핑한다:

```python
_RELATION_MAP = {
    "erode":    StackRelationType.ERODE,
    "onlap":    StackRelationType.ONLAP,
    "fault":    StackRelationType.FAULT,
    "basement": StackRelationType.BASEMENT,
}
```

### ID 매핑 로직

`extract_result()`에서 `lith_block`의 정수 ID를 element 이름으로 매핑한다:

```python
element_names = [e.name for g in groups for e in g.elements]
all_names = element_names + ["Basement"]
# ID 1 → all_names[0], ID 2 → all_names[1], ...
```

GemPy는 마지막 ID를 Basement에 자동 할당하므로, `element_names` 리스트 끝에 `"Basement"`를 추가한다.

---

## orientation.py 설계

### 3단계 폴백 전략

```
포인트 수 확인
    │
    ├─ n >= 3 → _fit_plane_normal()   (SVD 평면 피팅)
    │
    ├─ n == 2 → _gradient_from_two_points()  (외적 기반)
    │
    └─ n == 1 → (0, 0, 1)  (수평면 가정)
```

### SVD 평면 피팅 (_fit_plane_normal)

1. 포인트를 중심(centroid) 기준으로 이동 (centered)
2. SVD 분해: `U, S, Vh = np.linalg.svd(centered)`
3. `Vh`의 마지막 행 = 최소 특이값에 대응하는 벡터 = **법선벡터**

이 법선벡터가 데이터 포인트들의 분산이 가장 작은 방향이므로, 최적 피팅 평면의 법선이 된다.

### 2점 기울기 (_gradient_from_two_points)

1. 두 점의 차이 벡터 `diff` 계산
2. 수평 직교 벡터 `perp` 생성: `(-diff.y, diff.x, 0)`
3. 외적 `diff × perp` = 면의 법선벡터

두 점이 수평으로 동일한 위치에 있으면 (수직 시추공) 수평면을 가정한다.

### 법선 방향 보정

법선벡터의 z 성분이 음수이면 반전한다. 이는 법선이 항상 **상향**을 가리키도록 보장한다:

```python
if normal[2] < 0:
    normal = -normal
```

### pole_to_angles

극벡터 `(gx, gy, gz)`를 `(azimuth, dip)`로 변환한다:

```
dip     = arccos(gz)           # z 성분으로 경사 계산
azimuth = arctan2(gx, gy) % 360  # 수평 성분으로 방위각 계산
```

입력 벡터가 단위벡터가 아니어도 내부에서 정규화하므로 안전하다.

---

## 예외 계층 설계

```
GempygenError (기본 예외)
├── ValidationError (입력 검증 실패)
│     └── InsufficientPointsError (surface points 부족)
├── ComputationError (GemPy 계산 실패)
└── OrientationEstimationError (방위 추정 실패)
```

### GemPy 예외 래핑

`compute_gempy_model()`에서 GemPy가 발생시키는 모든 예외를 `ComputationError`로 래핑한다. 이를 통해 사용자는 GemPy의 내부 예외 구조를 알 필요 없이 `ComputationError`만 처리하면 된다.

```python
try:
    gp.compute_model(geo_model)
except Exception as e:
    raise ComputationError(f"GemPy computation failed: {e}") from e
```

`from e` 구문으로 원본 예외를 체인에 보존하므로, 디버깅 시 원인을 추적할 수 있다.
