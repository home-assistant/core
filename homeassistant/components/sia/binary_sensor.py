"""Module for SIA Binary Sensors."""
from __future__ import annotations

from collections.abc import Iterable
import logging

from pysiaalarm import SIAEvent

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    SIA_HUB_ZONE,
    SIA_UNIQUE_ID_FORMAT_BINARY,
)
from .sia_entity_base import SIABaseEntity
from .utils import SIABinarySensorEntityDescription, get_name

_LOGGER = logging.getLogger(__name__)


CC_POWER: dict[str, bool] = {
    "AT": False,
    "AR": True,
}

CC_SMOKE: dict[str, bool] = {
    "GA": True,
    "GH": False,
    "FA": True,
    "FH": False,
    "KA": True,
    "KH": False,
}

CC_MOISTURE: dict[str, bool] = {
    "WA": True,
    "WH": False,
}


def generate_binary_sensors(entry) -> Iterable[SIABinarySensor]:
    """Generate binary sensors.

    For each Account there is one power sensor with zone == 0.
    For each Zone in each Account there is one smoke and one moisture sensor.
    """
    for account_data in entry.data[CONF_ACCOUNTS]:
        yield SIABinarySensor(
            SIABinarySensorEntityDescription(
                key=SIA_UNIQUE_ID_FORMAT_BINARY.format(
                    entry.entry_id,
                    account_data[CONF_ACCOUNT],
                    SIA_HUB_ZONE,
                    BinarySensorDeviceClass.POWER,
                ),
                name=get_name(
                    port=entry.data[CONF_PORT],
                    account=account_data[CONF_ACCOUNT],
                    zone=SIA_HUB_ZONE,
                    device_class=BinarySensorDeviceClass.POWER,
                ),
                device_class=BinarySensorDeviceClass.POWER,
                entity_category="diagnostic",
                port=entry.data[CONF_PORT],
                account=account_data[CONF_ACCOUNT],
                zone=SIA_HUB_ZONE,
                ping_interval=account_data[CONF_PING_INTERVAL],
                code_consequences=CC_POWER,
                always_reset_availability=True,
            ),
        )
        zones = entry.options[CONF_ACCOUNTS][account_data[CONF_ACCOUNT]][CONF_ZONES]
        for zone in range(1, zones + 1):
            yield SIABinarySensor(
                SIABinarySensorEntityDescription(
                    key=SIA_UNIQUE_ID_FORMAT_BINARY.format(
                        entry.entry_id,
                        account_data[CONF_ACCOUNT],
                        zone,
                        BinarySensorDeviceClass.SMOKE,
                    ),
                    name=get_name(
                        port=entry.data[CONF_PORT],
                        account=account_data[CONF_ACCOUNT],
                        zone=zone,
                        device_class=BinarySensorDeviceClass.SMOKE,
                    ),
                    device_class=BinarySensorDeviceClass.SMOKE,
                    entity_registry_enabled_default=False,
                    port=entry.data[CONF_PORT],
                    account=account_data[CONF_ACCOUNT],
                    zone=zone,
                    ping_interval=account_data[CONF_PING_INTERVAL],
                    code_consequences=CC_SMOKE,
                    always_reset_availability=True,
                ),
            )
            yield SIABinarySensor(
                SIABinarySensorEntityDescription(
                    key=SIA_UNIQUE_ID_FORMAT_BINARY.format(
                        entry.entry_id,
                        account_data[CONF_ACCOUNT],
                        zone,
                        BinarySensorDeviceClass.MOISTURE,
                    ),
                    name=get_name(
                        port=entry.data[CONF_PORT],
                        account=account_data[CONF_ACCOUNT],
                        zone=zone,
                        device_class=BinarySensorDeviceClass.MOISTURE,
                    ),
                    device_class=BinarySensorDeviceClass.MOISTURE,
                    entity_registry_enabled_default=False,
                    port=entry.data[CONF_PORT],
                    account=account_data[CONF_ACCOUNT],
                    zone=zone,
                    ping_interval=account_data[CONF_PING_INTERVAL],
                    code_consequences=CC_MOISTURE,
                    always_reset_availability=True,
                ),
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SIA binary sensors from a config entry."""
    async_add_entities(generate_binary_sensors(entry))


class SIABinarySensor(SIABaseEntity, BinarySensorEntity):
    """Class for SIA Binary Sensors."""

    entity_description: SIABinarySensorEntityDescription

    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""
        if last_state is not None and last_state.state is not None:
            if last_state.state == STATE_ON:
                self._attr_is_on = True
            elif last_state.state == STATE_OFF:
                self._attr_is_on = False
            elif last_state.state == STATE_UNAVAILABLE:
                self._attr_available = False

    def update_state(self, sia_event: SIAEvent) -> bool:
        """Update the state of the binary sensor."""
        new_state = self.entity_description.code_consequences.get(sia_event.code, None)
        if new_state is None:
            return False
        _LOGGER.debug("New state will be %s", new_state)
        self._attr_is_on = new_state
        return True

    @callback
    def async_set_unavailable(self, _) -> None:
        """Set unavailable overridden to allow connectivity behaviour."""
        self._attr_available = False
        self.async_write_ha_state()
