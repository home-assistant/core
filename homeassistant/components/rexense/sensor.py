"""Platform for Rexense sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RexenseConfigEntry
from .const import DOMAIN, REXSENSE_SENSOR_TYPES
from .websocket_client import RexenseWebsocketClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RexenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Rexense sensors from a config entry."""
    client: RexenseWebsocketClient = entry.runtime_data
    entities: list[RexenseSensor] = []

    for sensor_type, sensor_info in REXSENSE_SENSOR_TYPES.items():
        name = sensor_info["name"]
        unit = sensor_info["unit"]
        device_class = sensor_info["device_class"]
        state_class = sensor_info["state_class"]

        # Filter by available attributes in feature_map
        for feature in client.feature_map:
            if sensor_type not in feature.get("Attributes", []):
                break
            # Use specialized name for three-phase meters
            if (
                "3PHASEMETER" in client.model
                or "3EM" in client.model
                or "3PM" in client.model
            ):
                name = sensor_info.get("name_spec", name)

            _LOGGER.debug("Adding sensor %s (%s)", name, sensor_type)
            entities.append(
                RexenseSensor(
                    client, sensor_type, name, unit, device_class, state_class
                )
            )

    async_add_entities(entities)


class RexenseSensor(SensorEntity):
    """Representation of a Rexense meter sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        client: RexenseWebsocketClient,
        sensor_type: str,
        name: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass,
    ) -> None:
        """Initialize the sensor."""
        self._client = client
        self._type = sensor_type

        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        # Unique ID: <DeviceId>_<sensor_type>
        self._attr_unique_id = f"{client.device_id}_{sensor_type}"

    async def async_added_to_hass(self) -> None:
        """When entity is added to registry."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._client.signal_update, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> StateType | None:
        """Return the current value of the sensor."""
        return self._client.last_values.get(self._type)

    @property
    def available(self) -> bool:
        """Return True if sensor data is available."""
        return getattr(self._client, "connected", False)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to link this sensor to the device."""
        return {
            "identifiers": {(DOMAIN, self._client.device_id)},
            "name": f"{self._client.model} ({self._client.device_id})",
            "manufacturer": "Rexense",
            "model": self._client.model,
        }
