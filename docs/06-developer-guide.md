# 개발자/기여자 가이드

GemPyGen 프로젝트에 기여하거나 확장하기 위한 실무 가이드이다.

---

## 개발 환경 설정

### 1. Python 버전 확인

```bash
python --version  # 3.10 이상 필요
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
# 코어 + 개발 의존성 (editable 모드)
pip install -e ".[dev]"

# 시각화 스크립트 사용 시 추가 설치
pip install matplotlib pyvista gempy-viewer
```

---

## 프로젝트 구조

```
src/gempygen/
├── __init__.py       # 공개 API export (21개 항목)
├── _version.py       # 버전 정의
├── schemas.py        # Pydantic 입출력 모델 (11개 클래스)
├── builder.py        # GeoModelBuilder + compute_model
├── engine.py         # GemPy 연동 (유일한 gempy import)
├── exporters.py      # 단면 경계선 추출
├── orientation.py    # SVD 기반 방위 자동 추정
└── exceptions.py     # 예외 계층 (5개 클래스)

tests/
├── test_builder.py       # Builder API 테스트
├── test_exporters.py     # 메시 내보내기 테스트
├── test_schemas.py       # Pydantic 스키마 검증 테스트
└── test_orientation.py   # 방위 추정 수학 테스트

scripts/
├── visualize.py      # 2D/3D 시각화 이미지 생성
└── report.py         # 입출력 요약 리포트

docs/                 # 문서
```

---

## 테스트

### 실행

```bash
# 전체 테스트 실행
pytest tests/

# 커버리지 측정
pytest --cov=gempygen tests/

# 특정 테스트 파일만 실행
pytest tests/test_schemas.py

# 특정 테스트 클래스/함수만 실행
pytest tests/test_builder.py::TestAddBorehole
```

### 테스트 구조

| 파일 | 대상 | GemPy 필요 |
|------|------|-----------|
| `test_schemas.py` | Pydantic 검증 로직 (범위, 해상도, 방위 등) | 아니오 |
| `test_builder.py` | Builder API, 입력 검증, `to_input()` | 아니오* |
| `test_exporters.py` | 단면 경계선 추출 | 아니오 |
| `test_orientation.py` | SVD 피팅, pole_to_angles, 폴백 전략 | 아니오 |

> *`test_builder.py`의 `TestComputeModel` 클래스는 `build_and_compute()`를 호출하므로 GemPy가 필요하다. 나머지 테스트 클래스(`TestAddBorehole`, `TestToInput` 등)는 GemPy 없이 실행 가능하다.

### 테스트 작성 패턴

```python
import pytest
from gempygen import GeoModelBuilder, BoreholeLayer

class TestNewFeature:
    def test_valid_input(self):
        """정상 입력이 올바르게 처리되는지 확인."""
        builder = GeoModelBuilder("test")
        builder.set_extent(0, 100, 0, 100, -300, 0)
        builder.add_borehole(0, 0, [
            BoreholeLayer(element="A", z=-100),
        ])
        input_data = builder.to_input()
        assert input_data.project_name == "test"

    def test_invalid_input_raises(self):
        """잘못된 입력이 적절한 예외를 발생시키는지 확인."""
        with pytest.raises(ValidationError):
            builder = GeoModelBuilder("test")
            builder.to_input()  # extent 미설정
```

---

## 코드 작성 규칙

### 타입 힌트

모든 모듈에서 `from __future__ import annotations`를 사용한다. 함수 시그니처에 반환 타입을 명시한다:

```python
from __future__ import annotations

def set_extent(self, x_min: float, x_max: float, ...) -> GeoModelBuilder:
    ...
```

### Docstring

한국어로 작성하되, 코드 요소(클래스명, 메서드명, 파라미터명)는 영어를 유지한다:

```python
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
    """
```

### Pydantic Field

제약 조건을 Field로 명시한다:

```python
element: str = Field(..., min_length=1)
nx: int = Field(default=50, gt=0, le=200)
ratio: float = Field(description="전체 셀 대비 비율 [0.0, 1.0]")
```

### 로깅

`print` 대신 `logging` 모듈을 사용한다:

```python
import logging
logger = logging.getLogger(__name__)

logger.warning("Element '%s': 1 point only", element_name)
```

---

## 확장 패턴

### 새로운 입력 필드 추가

예시: `GeoModelInput`에 `coordinate_system: Optional[str]` 필드를 추가하는 경우.

**1단계: `schemas.py`에 필드 추가**

```python
class GeoModelInput(BaseModel):
    ...
    coordinate_system: Optional[str] = Field(
        default=None,
        description="좌표계 (예: 'EPSG:5186')"
    )
```

**2단계: `builder.py`에 setter 추가**

```python
def set_coordinate_system(self, cs: str) -> GeoModelBuilder:
    """좌표계를 설정한다."""
    self._coordinate_system = cs
    return self
```

`to_input()`에서 새 필드를 `GeoModelInput`에 전달하고, `from_input()`에서 역방향으로 복원한다.

**3단계: `engine.py` 수정 (필요 시)**

새 필드가 GemPy 모델 생성에 영향을 준다면 `build_gempy_model()`에서 처리한다.

**4단계: 테스트 추가**

`test_schemas.py`에 검증 테스트, `test_builder.py`에 Builder 테스트를 추가한다.

**5단계: `__init__.py` 업데이트 (필요 시)**

새 클래스를 공개 API로 노출해야 하면 `__all__`에 추가한다.

---

## GemPy API 변경 대응

GemPy API가 변경되면 `engine.py`만 수정하면 된다. 다른 모듈은 GemPy를 직접 import하지 않으므로 영향을 받지 않는다.

확인 절차:

1. GemPy 새 버전 설치
2. `pytest tests/` 실행
3. 실패하는 테스트 확인 (대부분 `test_builder.py::TestComputeModel`)
4. `engine.py`의 해당 함수 수정
5. 테스트 재실행하여 통과 확인

---

## 알려진 제한사항

| 제한 | 설명 |
|------|------|
| 해상도 상한 | `ModelResolution`의 각 축은 최대 200. 초과 시 Pydantic 검증 오류 |
| 자동 방위 | element당 하나의 orientation만 추정. 곡면 모델링에는 한계 |
| 버전 불일치 | `_version.py`(0.1.0)와 `pyproject.toml`(0.2.0) 동기화 필요 |
