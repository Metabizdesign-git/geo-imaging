# 문제 해결 및 FAQ

GemPyGen 사용 시 발생할 수 있는 오류와 해결 방법, 자주 묻는 질문을 정리한다.

---

## 예외별 대처법

### ValidationError: "Extent not set"

```
gempygen.exceptions.ValidationError: Extent not set. Call set_extent() first.
```

**원인:** `build_and_compute()` 또는 `to_input()` 호출 전에 `set_extent()`를 호출하지 않았다.

**해결:**

```python
builder.set_extent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0)
```

---

### ValidationError: "No boreholes"

```
gempygen.exceptions.ValidationError: No boreholes. Call add_borehole() first.
```

**원인:** `add_borehole()`을 한 번도 호출하지 않았다.

**해결:** 최소 1개의 시추공을 추가한다.

```python
builder.add_borehole(0, 0, [
    BoreholeLayer(element="Sandstone", z=-100),
])
```

---

### Pydantic ValidationError: "x_min must be < x_max"

```
pydantic_core._pydantic_core.ValidationError: x_min (100) must be < x_max (0)
```

**원인:** `ModelExtent`의 최솟값이 최댓값 이상이다.

**해결:** min/max 순서를 확인한다. `x_min < x_max`, `y_min < y_max`, `z_min < z_max`여야 한다.

```python
# 올바른 예시
ModelExtent(x_min=0, x_max=100, y_min=0, y_max=100, z_min=-300, z_max=0)

# z축 주의: -300(깊은 곳) < 0(지표면)
```

---

### Pydantic ValidationError: Orientation

```
ValueError: Provide either (azimuth, dip, polarity) or (gx, gy, gz)
```

**원인:** `Orientation` 생성 시 각도 표현 `(azimuth, dip, polarity)`과 극벡터 표현 `(gx, gy, gz)` 중 어느 쪽도 완전하게 제공하지 않았다.

**해결:** 두 표현 중 하나를 모두 제공한다.

```python
# 각도 표현 — 세 값 모두 필요
Orientation(x=50, y=50, z=-100, azimuth=90, dip=30, polarity=1)

# 극벡터 표현 — 세 값 모두 필요
Orientation(x=50, y=50, z=-100, gx=0.5, gy=0.0, gz=0.866)
```

---

### Pydantic ValidationError: ModelResolution

```
Input should be less than or equal to 200
```

**원인:** 격자 해상도가 축당 최대 200을 초과한다.

**해결:** 해상도를 200 이하로 설정한다.

```python
builder.set_resolution(nx=100, ny=100, nz=100)  # 최대 200
```

---

### InsufficientPointsError

```
gempygen.exceptions.InsufficientPointsError: ...
```

**원인:** 특정 element의 surface points가 모델링에 필요한 최소 수보다 적다.

**해결:** 해당 element를 포함하는 시추공을 추가한다. 정확한 방위 추정을 위해 3개 이상의 시추공을 권장한다.

---

### ComputationError: "GemPy computation failed"

```
gempygen.exceptions.ComputationError: GemPy computation failed: ...
```

**원인:** GemPy 내부 계산 엔진 실패. 다양한 원인이 있을 수 있다.

**대처 순서:**

1. **좌표 확인:** 시추공 좌표가 extent 범위 내에 있는지 확인
   ```python
   for bh in builder._boreholes:
       assert builder._extent.x_min <= bh.x <= builder._extent.x_max
       assert builder._extent.y_min <= bh.y <= builder._extent.y_max
   ```

2. **해상도 낮추기:** 낮은 해상도로 재시도
   ```python
   builder.set_resolution(20, 20, 20)
   ```

3. **시추공 수 확인:** 3개 이상의 시추공 사용 권장

4. **방위 수동 설정:** 자동 추정 대신 명시적 방위 제공
   ```python
   builder.add_orientations("Sandstone", [
       Orientation(x=50, y=50, z=-100, azimuth=0, dip=0, polarity=1),
   ])
   ```

5. **원본 오류 확인:** `ComputationError`의 `__cause__`에서 GemPy 원본 예외 확인
   ```python
   try:
       result = builder.build_and_compute()
   except ComputationError as e:
       print(f"GemPy 원본 오류: {e.__cause__}")
   ```

---

### OrientationEstimationError

```
gempygen.exceptions.OrientationEstimationError: Failed to estimate orientation for 'X': ...
```

**원인:** SVD 평면 피팅 또는 기울기 계산 중 수치적 불안정이 발생했다.

**해결:** 해당 element에 명시적 방위를 제공한다.

```python
builder.add_orientations("X", [
    Orientation(x=50, y=50, z=-100, gx=0, gy=0, gz=1),  # 수평면
])
```

---

## 일반적인 문제

### 모델 결과가 기대와 다른 경우

1. **element 순서 확인:**
   ```python
   input_data = builder.to_input()
   print(input_data.discover_elements())
   ```
   시추공에서 element가 등장하는 순서가 결과의 ID 매핑에 영향을 준다.

2. **구조 그룹 확인:**
   ```python
   groups = input_data.resolve_structural_groups()
   for g in groups:
       print(f"  {g.name} ({g.relation}): {g.elements}")
   ```

3. **좌표 범위 확인:** 시추공 좌표가 extent 내에 있는지 확인

4. **시추공 수:** 의미 있는 3D 보간을 위해 3개 이상 권장

### 메모리 부족 (MemoryError)

- 해상도 낮추기: 100×100×100 이하 권장
- 전체 셀 수 확인: `nx × ny × nz`
- 64비트 Python 사용 확인

### ImportError: No module named 'gempy'

```bash
pip install gempy>=2024.0
pip install gempy-engine
```

Python 버전이 3.10 이상인지 확인한다.

### 시각화 스크립트 오류

**필수 패키지 미설치:**
```bash
pip install matplotlib pyvista gempy-viewer
```

**GUI 없는 환경 (서버/CI):**
- `visualize.py`는 `matplotlib.use('Agg')`와 `pv.OFF_SCREEN = True`를 자동 설정하므로 대부분의 환경에서 작동한다.
- PyVista가 렌더링 백엔드를 찾지 못하면 `xvfb` 설치가 필요할 수 있다.

---

## FAQ

### Q: 시추공은 최소 몇 개 필요한가?

최소 **1개**로 계산은 가능하다. 하지만 의미 있는 3D 모델을 위해 **3개 이상**을 권장한다.

- 1개: 수평면 가정 (dip=0). 실질적으로 수평 지층만 모델링 가능
- 2개: 두 점 기울기 기반 방위 추정. 한 방향의 기울기만 반영
- 3개 이상: SVD 평면 피팅. 3D 경사 방향을 정확하게 추정

### Q: 동일 시추공에서 같은 element가 여러 번 등장할 수 있는가?

`BoreholeLayer` 리스트에 동일 element를 여러 번 추가할 수 있다. 각각 별도의 surface point로 처리된다. 그러나 일반적으로 하나의 시추공에서 동일 element는 한 번만 관측된다.

### Q: z 값은 양수/음수 어느 쪽을 사용해야 하는가?

관례상 **지표면 = 0, 지하 = 음수**이다. 그러나 양수도 작동한다. `z_min < z_max` 조건만 충족하면 된다.

```python
# 일반적인 설정
set_extent(..., z_min=-300, z_max=0)      # 지표면=0, 지하=음수

# 양수도 가능
set_extent(..., z_min=0, z_max=300)        # 깊이를 양수로 표현
```

### Q: GemPy 없이 입력 검증만 할 수 있는가?

`to_input()` 또는 `GeoModelInput` 생성만으로 Pydantic 검증이 실행된다. `build_and_compute()`를 호출하기 전까지는 GemPy 계산이 수행되지 않는다.

```python
# 입력 검증만 수행 (GemPy 계산 없음)
input_data = builder.to_input()

# 또는
input_data = GeoModelInput(
    project_name="test",
    extent=ModelExtent(x_min=0, x_max=100, ...),
    boreholes=[...],
)
```

> 단, `builder.py`가 모듈 수준에서 `engine.py`를 import하고, `engine.py`가 `gempy`를 import하므로, `gempygen` 패키지 자체를 import하려면 gempy가 설치되어 있어야 한다.

### Q: 결과를 JSON으로 저장하려면?

`ModelResult`에는 `np.ndarray` 필드가 포함되어 있으므로 직접 JSON 직렬화가 불가능하다. `tolist()`로 변환해야 한다.

```python
import json

output = {
    "total_cells": result.total_cells,
    "lith_block": result.lith_block.tolist(),
    "lithology_stats": [
        {"id": s.id, "element_name": s.element_name,
         "cell_count": s.cell_count, "ratio": s.ratio}
        for s in result.lithology_stats
    ],
}

with open("result.json", "w") as f:
    json.dump(output, f)
```

자세한 내용은 [출력 데이터 활용 가이드](04-output-guide.md)를 참조한다.

### Q: 해상도를 200보다 높게 설정할 수 있는가?

현재 `ModelResolution`의 각 축은 **최대 200**으로 제한된다 (Pydantic Field 제약). 200×200×200 = 8,000,000 셀로, 이 이상의 해상도는 메모리와 계산 시간이 급격히 증가한다.

### Q: 구조 그룹을 설정하지 않으면 어떻게 되는가?

`set_group()`을 호출하지 않으면 모든 element가 **단일 erode 그룹("Default")**으로 자동 구성된다. 대부분의 단순한 퇴적층 모델에서는 이 기본값으로 충분하다. 단층이나 부정합이 있는 복잡한 모델에서만 명시적 그룹 설정이 필요하다.
