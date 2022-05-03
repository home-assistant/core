"""The Elro Connects siren platform."""
from __future__ import annotations

import logging

from elro.command import SILENCE_ALARM, TEST_ALARM
from elro.device import (
    ALARM_CO,
    ALARM_FIRE,
    ALARM_HEAT,
    ALARM_SMOKE,
    ALARM_WATER,
    ATTR_DEVICE_STATE,
    ATTR_DEVICE_TYPE,
    STATE_SILENCE,
    STATE_TEST_ALARM,
    STATES_OFFLINE,
    STATES_ON,
)

from homeassistant.components.siren import SirenEntity, SirenEntityDescription
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CONNECTOR_ID, DOMAIN
from .device import ElroConnectsEntity, ElroConnectsK1

_LOGGER = logging.getLogger(__name__)

SIREN_DEVICE_TYPES = {
    ALARM_CO: SirenEntityDescription(
        key=ALARM_CO,
        device_class="carbon_monoxide",
        name="CO Alarm",
        icon="mdi:molecule-co",
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
            ElroConnectsSiren(
                elro_connects_api,
                connector_id,
                device_id,
                SIREN_DEVICE_TYPES[attributes[ATTR_DEVICE_TYPE]],
            )
            for device_id, attributes in device_status.items()
            if attributes[ATTR_DEVICE_TYPE] in SIREN_DEVICE_TYPES
        ]
    )


class ElroConnectsSiren(ElroConnectsEntity, SirenEntity):
    """Elro Connects Fire Alarm Entity."""

    def __init__(
        self,
        elro_connects_api: ElroConnectsK1,
        connector_id: str,
        device_id: int,
        description: SirenEntityDescription,
    ) -> None:
        """Initialize a Fire Alarm Entity."""
        self._device_id = device_id
        self._elro_connects_api = elro_connects_api
        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
        )
        ElroConnectsEntity.__init__(
            self,
            elro_connects_api.coordinator,
            connector_id,
            device_id,
            description,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on or none if the device is offline."""
        if not self.data or self.data[ATTR_DEVICE_STATE] in STATES_OFFLINE:
            return None
        return self.data[ATTR_DEVICE_STATE] in STATES_ON

    async def async_turn_on(self, **kwargs) -> None:
        """Send a test alarm request."""
        _LOGGER.debug("Sending test alarm request for entity %s", self.entity_id)
        await self._elro_connects_api.async_connect()
        await self._elro_connects_api.async_process_command(
            TEST_ALARM, device_ID=self._device_id
        )

        self.data[ATTR_DEVICE_STATE] = STATE_TEST_ALARM
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Send a silence alarm request."""
        _LOGGER.debug("Sending silence alarm request for entity %s", self.entity_id)
        await self._elro_connects_api.async_connect()
        await self._elro_connects_api.async_process_command(
            SILENCE_ALARM, device_ID=self._device_id
        )

        self.data[ATTR_DEVICE_STATE] = STATE_SILENCE
        self.async_write_ha_state()
