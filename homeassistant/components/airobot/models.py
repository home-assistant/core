"""Models for the Airobot integration."""

from __future__ import annotations

from dataclasses import dataclass

from pyairobotrest.models import ThermostatSettings, ThermostatStatus


@dataclass
class AirobotData:
    """Data from the Airobot coordinator."""

    status: ThermostatStatus
    settings: ThermostatSettings
