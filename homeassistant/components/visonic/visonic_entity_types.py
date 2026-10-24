"""Global Types."""

from dataclasses import dataclass, field, fields
from typing import Any, cast, override

###################################################################################
############## Sensor Definitions for binary_sensor and sensor (for float) ########
############## State Classes: Panel, Sensor, Switch and Device ####################
###################################################################################


class DataclassDictMixin:
    """Base class for dictionary conversions."""

    def as_dict(self) -> dict[str, Any]:
        """Convert to a dict and flatten dict-valued fields."""
        data: dict[str, Any] = {}
        for f in fields(cast(Any, self)):
            value = getattr(self, f.name)
            if isinstance(value, dict):
                data.update(value)
            else:
                data[f.name] = value
        return data


@dataclass(slots=True)
class PanelState(DataclassDictMixin):
    """Internal panel state."""

    emulationmode: str
    trouble: str
    battery_level: int
    tamper: bool
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BaseData:
    """Base Sensor Data."""

    # This is the device identifier returned in the DeviceInfo to group sensors under a device
    identifier: str


@dataclass(slots=True)
class AlarmPanelData(BaseData):
    """Base Sensor Data."""

    @override
    def __str__(self) -> str:
        parts = [
            f"identifier={self.identifier!r}",
        ]
        return ", ".join(parts)
