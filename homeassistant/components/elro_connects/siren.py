"""The Elro Connects siren platform."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.siren import SirenEntity, SirenEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ALARM_CO,
    ALARM_FIRE,
    ALARM_HEAT,
    ALARM_SMOKE,
    ALARM_WATER,
    ATTR_DEVICE_TYPE,
    CONF_CONNECTOR_ID,
    DEVICE_STATE,
    DOMAIN,
)
from .device import ElroConnectsEntity, ElroConnectsK1

_LOGGER = logging.getLogger(__name__)

SIREN_DEVICE_TYPES = {
    ALARM_CO: SirenEntityDescription(
        key=ALARM_CO,
        device_class="carbon_monoxide",
        name="CO2 Alarm",
        icon="mdi:molecule-co2",
    ),
    ALARM_FIRE: SirenEntityDescription(
        key=ALARM_FIRE,
        device_class="smoke",
        name="Fire Alarm",
        icon="mdi:fire-alert",
    ),
    ALARM_HEAT: SirenEntityDescription(
        key=ALARM_HEAT,
        device_class="heat",
        name="Heat Alarm",
        icon="mdi:fire-alert",
    ),
    ALARM_SMOKE: SirenEntityDescription(
        key=ALARM_SMOKE,
        device_class="smoke",
        name="Smoke Alarm",
        icon="mdi:smoke",
    ),
    ALARM_WATER: SirenEntityDescription(
        key=ALARM_WATER,
        device_class="moisture",
        name="Water Alarm",
        icon="mid:water-alert",
    ),
}
SIREN_ATTRIBUTES = ["signal", "battery", "device_state"]
SIREN_ON_STATES = ["ALARM", "TEST ALARM"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    elro_connects_api: ElroConnectsK1 = hass.data[DOMAIN][config_entry.entry_id]
    connector_id: str = config_entry.data[CONF_CONNECTOR_ID]
    device_status: dict[int, dict] = elro_connects_api.coordinator.data

    async_add_entities(
        [
            ElroConnectsFireAlarm(
                elro_connects_api.coordinator,
                connector_id,
                device_id,
                SIREN_DEVICE_TYPES[attributes[ATTR_DEVICE_TYPE]],
            )
            for device_id, attributes in device_status.items()
            if attributes[ATTR_DEVICE_TYPE] in SIREN_DEVICE_TYPES
        ]
    )


class ElroConnectsFireAlarm(ElroConnectsEntity, SirenEntity):
    """Elro Connects Fire Alarm Entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        connector_id: str,
        device_id: int,
        description: SirenEntityDescription,
    ) -> None:
        """Initialize a Fire Alarm Entity."""
        self._coordinator = coordinator
        self._description = description
        self._state = False
        self._device_id = device_id
        self._data: dict = coordinator.data[self._device_id]
        self._attr_device_class = description.device_class
        self._attr_icon = description.icon
        ElroConnectsEntity.__init__(self, coordinator, connector_id, device_id)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return state attributes."""
        if not self._data:
            return None
        return {key: val for key, val in self._data.items() if key in SIREN_ATTRIBUTES}

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._data[DEVICE_STATE] in SIREN_ON_STATES if self._data else False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return (
            self._data[ATTR_NAME] if ATTR_NAME in self._data else self._description.name
        )

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._data = self._coordinator.data[self._device_id]
        self.async_write_ha_state()
