"""NetgearPy models for device settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from mashumaro import field_options
from mashumaro.mixins.orjson import DataClassORJSONMixin


@dataclass
class Battery(DataClassORJSONMixin):
    """Battery model."""

    identifier: str = field(metadata=field_options(alias="id"))
    name: str
    serial_number: str


@dataclass
class BatteryListResponse(DataClassORJSONMixin):
    """Battery list response."""

    batteries: list[Battery]


class OnlineStatus(StrEnum):
    """Online status."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class SmartMode(StrEnum):
    """Smart mode."""

    DYNAMIC = "DYNAMIC"


@dataclass
class CurrentPower(DataClassORJSONMixin):
    """Current power model."""

    state_of_charge: float = field(metadata=field_options(alias="soc"))
    on_grid: bool = field(metadata=field_options(alias="onGrid"))
    online_status: OnlineStatus = field(metadata=field_options(alias="onlineStatus"))


@dataclass
class BatteryState(DataClassORJSONMixin):
    """Battery state."""

    serial_number: str = field(metadata=field_options(alias="sn"))
    name: str
    longitude: float
    latitude: float
    online_status: OnlineStatus = field(metadata=field_options(alias="onlineStatus"))
    current_power: CurrentPower = field(metadata=field_options(alias="currentPower"))
    smart_mode: SmartMode = field(metadata=field_options(alias="smartMode"))


@dataclass
class OnlineStatusResponse(DataClassORJSONMixin):
    """Online state."""

    serial_number: str = field(metadata=field_options(alias="sn"))
    online_status: OnlineStatus = field(metadata=field_options(alias="onlineStatus"))


@dataclass
class PhotovoltaicData(DataClassORJSONMixin):
    """Photovoltaic data."""

    name: str
    power: int


@dataclass
class GlobalSettings(DataClassORJSONMixin):
    """Global settings."""

    max_output: int = field(metadata=field_options(alias="maxOutput"))
    max_output_limit: int = field(metadata=field_options(alias="maxOutputLimit"))
    max_output_unlocked: bool = field(metadata=field_options(alias="maxOutputUnlocked"))
    battery_high_capacity: int = field(metadata=field_options(alias="batHighCap"))
    battery_use_capacity: int = field(metadata=field_options(alias="batUseCap"))
    maximum_charge_power: int = field(metadata=field_options(alias="maxChargePower"))
