class GempygenError(Exception):
    """Base exception for all gempygen SDK errors."""


class ValidationError(GempygenError, ValueError):
    """Raised when input data fails validation."""


class InsufficientPointsError(ValidationError):
    """Raised when a structural element has fewer surface points than required."""


class ComputationError(GempygenError):
    """Raised when the GemPy computation engine fails."""


class OrientationEstimationError(GempygenError):
    """Raised when orientation auto-estimation fails."""
