"""UniFi speedtest hub helpers.

The coordinator is at the top-level coordinator module to satisfy
the hass-enforce-class-module linting rule.
"""

from ..coordinator import UnifiSpeedtestCoordinator

__all__ = ["UnifiSpeedtestCoordinator"]
