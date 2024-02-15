"""Implementation of the Radarr sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity


class OverseerrSensor(SensorEntity):
    """Implementation of the Radarr sensor."""

    def __init__(self, coordinator, idx):
        """Implementation of the Radarr sensor."""  # noqa: D401
        super().__init__(coordinator, context=idx)
        self.idx = idx
