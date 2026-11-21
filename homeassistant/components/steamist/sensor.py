"""Support for Steamist sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiosteamist import (
    MODEL_550,
    PROFILE_OFF,
    PROFILE_SHOWER_1,
    PROFILE_SHOWER_2,
    PROFILE_STEAM_1,
    PROFILE_STEAM_2,
    SteamistStatus,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_MODEL, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SteamistConfigEntry, SteamistDataUpdateCoordinator
from .entity import SteamistEntity

_KEY_MINUTES_REMAIN = "minutes_remain"
_KEY_TEMP = "temp"
_KEY_ACTIVE_PROFILE = "active_profile"

UNIT_MAPPINGS = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
}

PROFILE_MAPPINGS: dict[int | None, str] = {
    PROFILE_OFF: "off",
    PROFILE_STEAM_1: "steam_profile_1",
    PROFILE_STEAM_2: "steam_profile_2",
    PROFILE_SHOWER_1: "shower_profile_1",
    PROFILE_SHOWER_2: "shower_profile_2",
}


@dataclass(frozen=True, kw_only=True)
class SteamistSensorEntityDescription(SensorEntityDescription):
    """Describes a Steamist sensor entity."""

    value_fn: Callable[[SteamistStatus], int | str | None]


SENSORS: tuple[SteamistSensorEntityDescription, ...] = (
    SteamistSensorEntityDescription(
        key=_KEY_MINUTES_REMAIN,
        translation_key="steam_minutes_remain",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda status: status.minutes_remain,
    ),
    SteamistSensorEntityDescription(
        key=_KEY_TEMP,
        translation_key="steam_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temp,
    ),
)

ACTIVE_PROFILE_SENSOR = SteamistSensorEntityDescription(
    key=_KEY_ACTIVE_PROFILE,
    translation_key="active_profile",
    device_class=SensorDeviceClass.ENUM,
    options=list(PROFILE_MAPPINGS.values()),
    value_fn=lambda status: PROFILE_MAPPINGS.get(status.profile, "off"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SteamistConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = config_entry.runtime_data
    descriptions: list[SteamistSensorEntityDescription] = list(SENSORS)
    if (
        config_entry.data.get(CONF_MODEL) == MODEL_550
        or coordinator.client.model == MODEL_550
    ):
        descriptions.append(ACTIVE_PROFILE_SENSOR)
    async_add_entities(
        [
            SteamistSensorEntity(coordinator, config_entry, description)
            for description in descriptions
        ]
    )


class SteamistSensorEntity(SteamistEntity, SensorEntity):
    """Representation of a Steamist sensor."""

    entity_description: SteamistSensorEntityDescription

    def __init__(
        self,
        coordinator: SteamistDataUpdateCoordinator,
        entry: SteamistConfigEntry,
        description: SteamistSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, entry, description)
        if description.key == _KEY_TEMP:
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS[
                self._status.temp_units
            ]

    @property
    @override
    def native_value(self) -> int | str | None:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self._status)
