"""gempygen — Geological Modeling SDK powered by GemPy.

시추공(borehole) 기반 입력으로 3D 지질 모델을 생성한다.

Basic usage::

    from gempygen import GeoModelBuilder, BoreholeLayer

    result = (
        GeoModelBuilder("simple_model")
        .set_extent(0, 100, 0, 100, -300, 0)
        .add_borehole(0, 0, [BoreholeLayer(element="Sandstone", z=-100), BoreholeLayer(element="Limestone", z=-200)])
        .add_borehole(100, 0, [BoreholeLayer(element="Sandstone", z=-120), BoreholeLayer(element="Limestone", z=-220)])
        .add_borehole(0, 100, [BoreholeLayer(element="Sandstone", z=-110), BoreholeLayer(element="Limestone", z=-210)])
        .build_and_compute()
    )

    print(result.lith_block.shape)
    for stat in result.lithology_stats:
        print(f"  {stat.element_name}: {stat.cell_count} cells ({stat.ratio:.1%})")
"""

from ._version import __version__
from .builder import GeoModelBuilder, compute_model
from .exporters import to_section_json
from .exceptions import (
    ComputationError,
    GempygenError,
    InsufficientPointsError,
    OrientationEstimationError,
    ValidationError,
)
from .schemas import (
    Borehole,
    BoreholeLayer,
    GeoModelInput,
    LithologyStats,
    ModelExtent,
    ModelResolution,
    ModelResult,
    Orientation,
    StructuralGroupConfig,
)

__all__ = [
    "__version__",
    # API
    "compute_model",
    "to_section_json",
    # Builder
    "GeoModelBuilder",
    # Input schemas
    "GeoModelInput",
    "ModelExtent",
    "ModelResolution",
    "Borehole",
    "BoreholeLayer",
    "StructuralGroupConfig",
    "Orientation",
    # Output schemas
    "ModelResult",
    "LithologyStats",
    # Exceptions
    "GempygenError",
    "ValidationError",
    "InsufficientPointsError",
    "ComputationError",
    "OrientationEstimationError",
]
