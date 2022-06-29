"""Support for IKEA Tradfri sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pytradfri.command import Command
from pytradfri.device import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    TIME_HOURS,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseEntity
from .const import (
    CONF_GATEWAY_ID,
    COORDINATOR,
    COORDINATOR_LIST,
    DOMAIN,
    KEY_API,
    LOGGER,
)
from .coordinator import TradfriDeviceDataUpdateCoordinator


@dataclass
class TradfriSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value: Callable[[Device], Any | None]


@dataclass
class TradfriSensorEntityDescription(
    SensorEntityDescription,
    TradfriSensorEntityDescriptionMixin,
):
    """Class describing Tradfri sensor entities."""


def _get_air_quality(device: Device) -> int | None:
    """Fetch the air quality value."""
    if (
        device.air_purifier_control.air_purifiers[0].air_quality == 65535
    ):  # The sensor returns 65535 if the fan is turned off
        return None

    return cast(int, device.air_purifier_control.air_purifiers[0].air_quality)


def _get_filter_time_left(device: Device) -> int:
    """Fetch the filter's remaining life (in hours)."""
    return round(
        device.air_purifier_control.air_purifiers[0].filter_lifetime_remaining / 60
    )


SENSOR_DESCRIPTIONS_BATTERY: tuple[TradfriSensorEntityDescription, ...] = (
    TradfriSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value=lambda device: cast(int, device.device_info.battery_level),
    ),
)


SENSOR_DESCRIPTIONS_FAN: tuple[TradfriSensorEntityDescription, ...] = (
    TradfriSensorEntityDescription(
        key="aqi",
        name="air quality",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value=_get_air_quality,
    ),
    TradfriSensorEntityDescription(
        key="filter_life_remaining",
        name="filter time left",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TIME_HOURS,
        icon="mdi:clock-outline",
        value=_get_filter_time_left,
    ),
)


@callback
def _migrate_old_unique_ids(hass: HomeAssistant, old_unique_id: str, key: str) -> None:
    """Migrate unique IDs to the new format."""
    ent_reg = entity_registry.async_get(hass)

    entity_id = ent_reg.async_get_entity_id(Platform.SENSOR, DOMAIN, old_unique_id)

    if entity_id is None:
        return

    new_unique_id = f"{old_unique_id}-{key}"

    try:
        ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
    except ValueError:
        LOGGER.warning(
            "Skip migration of id [%s] to [%s] because it already exists",
            old_unique_id,
            new_unique_id,
        )
        return

    LOGGER.debug(
        "Migrating unique_id from [%s] to [%s]",
        old_unique_id,
        new_unique_id,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Tradfri config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    coordinator_data = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    api = coordinator_data[KEY_API]

    entities: list[TradfriSensor] = []

    for device_coordinator in coordinator_data[COORDINATOR_LIST]:
        if (
            not device_coordinator.device.has_light_control
            and not device_coordinator.device.has_socket_control
            and not device_coordinator.device.has_signal_repeater_control
            and not device_coordinator.device.has_air_purifier_control
        ):
            descriptions = SENSOR_DESCRIPTIONS_BATTERY
        elif device_coordinator.device.has_air_purifier_control:
            descriptions = SENSOR_DESCRIPTIONS_FAN
        else:
            continue

        for description in descriptions:
            # Added in Home assistant 2022.3
            _migrate_old_unique_ids(
                hass=hass,
                old_unique_id=f"{gateway_id}-{device_coordinator.device.id}",
                key=description.key,
            )

            entities.append(
                TradfriSensor(
                    device_coordinator,
                    api,
                    gateway_id,
                    description=description,
                )
            )

    async_add_entities(entities)


class TradfriSensor(TradfriBaseEntity, SensorEntity):
    """The platform class required by Home Assistant."""

    entity_description: TradfriSensorEntityDescription

    def __init__(
        self,
        device_coordinator: TradfriDeviceDataUpdateCoordinator,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
        description: TradfriSensorEntityDescription,
    ) -> None:
        """Initialize a Tradfri sensor."""
        super().__init__(
            device_coordinator=device_coordinator,
            api=api,
            gateway_id=gateway_id,
        )

        self.entity_description = description

        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"

        if description.name:
            self._attr_name = f"{self._attr_name}: {description.name}"

        self._refresh()  # Set initial state

    def _refresh(self) -> None:
        """Refresh the device."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
