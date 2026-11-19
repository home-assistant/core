"""Internal functionality not part of HA infrastructure."""

from .api import get_axis_api, is_companion_device
from .hub import AxisHub

__all__ = ["AxisHub", "get_axis_api", "is_companion_device"]
