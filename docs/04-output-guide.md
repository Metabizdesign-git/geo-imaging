# 출력 데이터 활용 가이드

`build_and_compute()` 또는 `compute_model()` 호출 후 반환되는 `ModelResult`의 각 필드를 해석하고 활용하는 방법을 다룬다.

---

## ModelResult 구조 개요

| 필드 | 타입 | 차원 | 설명 |
|------|------|------|------|
| `lith_block` | `np.ndarray` | `(total_cells,)` | 셀별 암상 ID |
| `scalar_field_matrix` | `np.ndarray` | `(n_groups, total_cells)` | 스칼라 필드 |
| `lithology_stats` | `list[LithologyStats]` | — | 암상별 통계 |
| `total_cells` | `int` | — | 전체 셀 수 (nx×ny×nz) |
| `resolution` | `list[int]` | `[nx, ny, nz]` | 격자 해상도 |
| `extent` | `list[float]` | 6개 | 공간 범위 |
| `element_names` | `list[str]` | — | 구조 요소 이름 목록 |

---

## lith_block 활용

### 1D → 3D 변환

`lith_block`은 3D 격자를 1차원으로 평탄화한 배열이다.

```python
import numpy as np

nx, ny, nz = result.resolution
block_3d = result.lith_block.reshape(nx, ny, nz)
```

### 수평 단면 (특정 깊이)

```python
# 깊이 인덱스 선택 (0=z_min, nz-1=z_max)
z_index = nz // 2
horizontal = block_3d[:, :, z_index]

# matplotlib로 시각화
import matplotlib.pyplot as plt
plt.imshow(horizontal.T, origin="lower", cmap="viridis")
plt.colorbar(label="Lithology ID")
plt.xlabel("X index")
plt.ylabel("Y index")
plt.title(f"Z index = {z_index}")
plt.savefig("horizontal_slice.png")
```

### 수직 단면 (X 고정)

```python
x_index = nx // 2
vertical_xz = block_3d[x_index, :, :]

plt.imshow(vertical_xz.T, origin="lower", cmap="viridis", aspect="auto")
plt.xlabel("Y index")
plt.ylabel("Z index")
plt.title(f"X index = {x_index}")
plt.savefig("vertical_slice_xz.png")
```

### 수직 단면 (Y 고정)

```python
y_index = ny // 2
vertical_yz = block_3d[:, y_index, :]

plt.imshow(vertical_yz.T, origin="lower", cmap="viridis", aspect="auto")
plt.xlabel("X index")
plt.ylabel("Z index")
plt.title(f"Y index = {y_index}")
plt.savefig("vertical_slice_yz.png")
```

### 암상 ID 매핑

```python
id_to_name = {}
for i, name in enumerate(result.element_names, start=1):
    id_to_name[i] = name
id_to_name[len(result.element_names) + 1] = "Basement"
```

### 특정 암상의 분포 마스크

```python
# Sandstone (ID=2) 영역만 추출
sandstone_id = 2
sandstone_mask = (block_3d == sandstone_id)
sandstone_volume_ratio = sandstone_mask.sum() / block_3d.size
print(f"Sandstone 체적 비율: {sandstone_volume_ratio:.1%}")
```

---

## scalar_field_matrix 활용

### 차원 구조

```python
sf = result.scalar_field_matrix
print(f"shape: {sf.shape}")  # (n_groups, total_cells)

# 첫 번째 그룹의 스칼라 필드
group_0 = sf[0]

# 3D로 변환
sf_3d = group_0.reshape(nx, ny, nz)
```

### 등치면 값의 의미

스칼라 필드의 등치면이 지질 경계를 정의한다. 특정 값을 기준으로 경계를 확인할 수 있다:

```python
# 스칼라 필드 범위 확인
print(f"min: {sf.min():.2f}, max: {sf.max():.2f}")

# 중간 깊이에서의 스칼라 값 분포
mid_z = sf_3d[:, :, nz // 2]
plt.imshow(mid_z.T, origin="lower", cmap="coolwarm")
plt.colorbar(label="Scalar value")
plt.savefig("scalar_field_slice.png")
```

---

## lithology_stats 활용

### 기본 출력

```python
for stat in result.lithology_stats:
    print(f"  ID={stat.id} {stat.element_name}: "
          f"{stat.cell_count:,} cells ({stat.ratio:.1%})")
```

### pandas DataFrame 변환

```python
import pandas as pd

df = pd.DataFrame([
    {
        "id": s.id,
        "element": s.element_name,
        "cells": s.cell_count,
        "ratio": s.ratio,
    }
    for s in result.lithology_stats
])

print(df.to_string(index=False))
```

### 체적 분석

```python
# 공간 범위에서 셀당 체적 계산
x_range = result.extent[1] - result.extent[0]
y_range = result.extent[3] - result.extent[2]
z_range = result.extent[5] - result.extent[4]
nx, ny, nz = result.resolution

cell_volume = (x_range / nx) * (y_range / ny) * (z_range / nz)

for stat in result.lithology_stats:
    volume = stat.cell_count * cell_volume
    print(f"  {stat.element_name}: {volume:,.0f} m³")
```

---

## scripts 활용

### report.py — 입출력 요약

```python
from gempygen.engine import build_gempy_model, compute_gempy_model

# GemPy 모델 객체가 필요 (ModelResult가 아님)
geo_model = build_gempy_model(builder.to_input())
compute_gempy_model(geo_model)

from scripts.report import print_input_summary, print_output_summary

print_input_summary(geo_model)   # Surface Points, Orientations, Grid 표
print_output_summary(geo_model)  # Lithology Block 통계, Scalar Field
```

### visualize.py — 이미지 생성

```python
from scripts.visualize import save_2d_sections, save_3d_surfaces

save_2d_sections(geo_model, "sections_2d.png")   # 2D 단면도
save_3d_surfaces(geo_model, "surfaces_3d.png")    # 3D 표면 렌더링
```

**필수 패키지:**

```bash
pip install matplotlib pyvista gempy-viewer
```

서버/CI 환경(GUI 없음)에서는 오프스크린 렌더링이 자동 설정된다 (`matplotlib.use('Agg')`, `pv.OFF_SCREEN = True`).
