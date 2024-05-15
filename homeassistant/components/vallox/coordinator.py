"""Coordinator for Vallox ventilation units."""

from __future__ import annotations

from vallox_websocket_api import MetricData

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class ValloxDataUpdateCoordinator(DataUpdateCoordinator[MetricData]):
    """The DataUpdateCoordinator for Vallox."""
