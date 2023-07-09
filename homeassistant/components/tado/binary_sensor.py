"""Support for Tado sensors for each zone."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DATA,
    DOMAIN,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TYPE_AIR_CONDITIONING,
    TYPE_BATTERY,
    TYPE_HEATING,
    TYPE_HOT_WATER,
    TYPE_POWER,
)
from .entity import TadoDeviceEntity, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class TadoBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    state_fn: Callable[[Any], bool]


@dataclass
class TadoBinarySensorEntityDescription(
    BinarySensorEntityDescription, TadoBinarySensorEntityDescriptionMixin
):
    """Describes Tado binary sensor entity."""

    attributes_fn: Callable[[Any], dict[Any, StateType]] | None = None


BATTERY_STATE_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="battery state",
    state_fn=lambda data: data["batteryState"] == "LOW",
    device_class=BinarySensorDeviceClass.BATTERY,
)
CONNECTION_STATE_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="connection state",
    translation_key="connection_state",
    state_fn=lambda data: data.get("connectionState", {}).get("value", False),
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)
POWER_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="power",
    state_fn=lambda data: data.power == "ON",
    device_class=BinarySensorDeviceClass.POWER,
)
LINK_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="link",
    state_fn=lambda data: data.link == "ONLINE",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)
OVERLAY_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="overlay",
    translation_key="overlay",
    state_fn=lambda data: data.overlay_active,
    attributes_fn=lambda data: {"termination": data.overlay_termination_type}
    if data.overlay_active
    else {},
    device_class=BinarySensorDeviceClass.POWER,
)
OPEN_WINDOW_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="open window",
    state_fn=lambda data: bool(data.open_window or data.open_window_detected),
    attributes_fn=lambda data: data.open_window_attr,
    device_class=BinarySensorDeviceClass.WINDOW,
)
EARLY_START_ENTITY_DESCRIPTION = TadoBinarySensorEntityDescription(
    key="early start",
    translation_key="early_start",
    state_fn=lambda data: data.preparation,
    device_class=BinarySensorDeviceClass.POWER,
)

DEVICE_SENSORS = {
    TYPE_BATTERY: [
        BATTERY_STATE_ENTITY_DESCRIPTION,
        CONNECTION_STATE_ENTITY_DESCRIPTION,
    ],
    TYPE_POWER: [
        CONNECTION_STATE_ENTITY_DESCRIPTION,
    ],
}

ZONE_SENSORS = {
    TYPE_HEATING: [
        POWER_ENTITY_DESCRIPTION,
        LINK_ENTITY_DESCRIPTION,
        OVERLAY_ENTITY_DESCRIPTION,
        OPEN_WINDOW_ENTITY_DESCRIPTION,
        EARLY_START_ENTITY_DESCRIPTION,
    ],
    TYPE_AIR_CONDITIONING: [
        POWER_ENTITY_DESCRIPTION,
        LINK_ENTITY_DESCRIPTION,
        OVERLAY_ENTITY_DESCRIPTION,
        OPEN_WINDOW_ENTITY_DESCRIPTION,
    ],
    TYPE_HOT_WATER: [
        POWER_ENTITY_DESCRIPTION,
        LINK_ENTITY_DESCRIPTION,
        OVERLAY_ENTITY_DESCRIPTION,
    ],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tado sensor platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]
    devices = tado.devices
    zones = tado.zones
    entities: list[BinarySensorEntity] = []

    # Create device sensors
    for device in devices:
        if "batteryState" in device:
            device_type = TYPE_BATTERY
        else:
            device_type = TYPE_POWER

        entities.extend(
            [
                TadoDeviceBinarySensor(tado, device, entity_description)
                for entity_description in DEVICE_SENSORS[device_type]
            ]
        )

    # Create zone sensors
    for zone in zones:
        zone_type = zone["type"]
        if zone_type not in ZONE_SENSORS:
            _LOGGER.warning("Unknown zone type skipped: %s", zone_type)
            continue

        entities.extend(
            [
                TadoZoneBinarySensor(tado, zone["name"], zone["id"], entity_description)
                for entity_description in ZONE_SENSORS[zone_type]
            ]
        )

    async_add_entities(entities, True)


class TadoDeviceBinarySensor(TadoDeviceEntity, BinarySensorEntity):
    """Representation of a tado Sensor."""

    entity_description: TadoBinarySensorEntityDescription

    def __init__(
        self, tado, device_info, entity_description: TadoBinarySensorEntityDescription
    ) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        self._tado = tado
        super().__init__(device_info)

        self._attr_unique_id = (
            f"{entity_description.key} {self.device_id} {tado.home_id}"
        )

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "device", self.device_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_device_data()

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_device_data()
        self.async_write_ha_state()

    @callback
    def _async_update_device_data(self):
        """Handle update callbacks."""
        try:
            self._device_info = self._tado.data["device"][self.device_id]
        except KeyError:
            return

        self._attr_is_on = self.entity_description.state_fn(self._device_info)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                self._device_info
            )


class TadoZoneBinarySensor(TadoZoneEntity, BinarySensorEntity):
    """Representation of a tado Sensor."""

    entity_description: TadoBinarySensorEntityDescription

    def __init__(
        self,
        tado,
        zone_name,
        zone_id,
        entity_description: TadoBinarySensorEntityDescription,
    ) -> None:
        """Initialize of the Tado Sensor."""
        self.entity_description = entity_description
        self._tado = tado
        super().__init__(zone_name, tado.home_id, zone_id)

        self._attr_unique_id = f"{entity_description.key} {zone_id} {tado.home_id}"

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "zone", self.zone_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_zone_data()

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_zone_data()
        self.async_write_ha_state()

    @callback
    def _async_update_zone_data(self):
        """Handle update callbacks."""
        try:
            tado_zone_data = self._tado.data["zone"][self.zone_id]
        except KeyError:
            return

        self._attr_is_on = self.entity_description.state_fn(tado_zone_data)
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                tado_zone_data
            )
