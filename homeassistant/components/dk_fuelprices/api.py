"""Backward-compatible imports for the dk_fuelprices coordinator."""

from .coordinator import SCAN_INTERVAL, APIClient

__all__ = ["SCAN_INTERVAL", "APIClient"]
