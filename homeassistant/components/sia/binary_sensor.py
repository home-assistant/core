"""Module for SIA Binary Sensors."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import logging

from pysiaalarm import SIAEvent

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    KEY_MOISTURE,
    KEY_POWER,
    KEY_SMOKE,
    SIA_HUB_ZONE,
    SIA_NAME_FORMAT,
    SIA_NAME_FORMAT_HUB,
    SIA_UNIQUE_ID_FORMAT_BINARY,
)
from .sia_entity_base import SIABaseEntity, SIAEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class SIABinarySensorEntityDescription(
    BinarySensorEntityDescription,
    SIAEntityDescription,
):
    """Describes SIA sensor entity."""


ENTITY_DESCRIPTION_POWER = SIABinarySensorEntityDescription(
    key=KEY_POWER,
    device_class=BinarySensorDeviceClass.POWER,
    entity_category=EntityCategory.DIAGNOSTIC,
    code_consequences={
        "AT": False,
        "AR": True,
    },
)

ENTITY_DESCRIPTION_SMOKE = SIABinarySensorEntityDescription(
    key=KEY_SMOKE,
    device_class=BinarySensorDeviceClass.SMOKE,
    code_consequences={
        "GA": True,
        "GH": False,
        "FA": True,
        "FH": False,
        "KA": True,
        "KH": False,
    },
    entity_registry_enabled_default=False,
)

ENTITY_DESCRIPTION_MOISTURE = SIABinarySensorEntityDescription(
    key=KEY_MOISTURE,
    device_class=BinarySensorDeviceClass.MOISTURE,
    code_consequences={
        "WA": True,
        "WH": False,
    },
    entity_registry_enabled_default=False,
)


def generate_binary_sensors(entry) -> Iterable[SIABinarySensor]:
    """Generate binary sensors.

    For each Account there is one power sensor with zone == 0.
    For each Zone in each Account there is one smoke and one moisture sensor.
    """
    for account_data in entry.data[CONF_ACCOUNTS]:
        yield SIABinarySensor(
            port=entry.data[CONF_PORT],
            account=account_data[CONF_ACCOUNT],
            zone=SIA_HUB_ZONE,
            ping_interval=account_data[CONF_PING_INTERVAL],
            entity_description=ENTITY_DESCRIPTION_POWER,
            unique_id=SIA_UNIQUE_ID_FORMAT_BINARY.format(
                entry.entry_id,
                account_data[CONF_ACCOUNT],
                SIA_HUB_ZONE,
                ENTITY_DESCRIPTION_POWER.device_class,
            ),
            name=SIA_NAME_FORMAT_HUB.format(
                entry.data[CONF_PORT],
                account_data[CONF_ACCOUNT],
                ENTITY_DESCRIPTION_POWER.device_class,
            ),
        )
        zones = entry.options[CONF_ACCOUNTS][account_data[CONF_ACCOUNT]][CONF_ZONES]
        for zone in range(1, zones + 1):
            yield SIABinarySensor(
                port=entry.data[CONF_PORT],
                account=account_data[CONF_ACCOUNT],
                zone=zone,
                ping_interval=account_data[CONF_PING_INTERVAL],
                entity_description=ENTITY_DESCRIPTION_SMOKE,
                unique_id=SIA_UNIQUE_ID_FORMAT_BINARY.format(
                    entry.entry_id,
                    account_data[CONF_ACCOUNT],
                    zone,
                    ENTITY_DESCRIPTION_SMOKE.device_class,
                ),
                name=SIA_NAME_FORMAT.format(
                    entry.data[CONF_PORT],
                    account_data[CONF_ACCOUNT],
                    zone,
                    ENTITY_DESCRIPTION_SMOKE.device_class,
                ),
            )
            yield SIABinarySensor(
                port=entry.data[CONF_PORT],
                account=account_data[CONF_ACCOUNT],
                zone=zone,
                ping_interval=account_data[CONF_PING_INTERVAL],
                entity_description=ENTITY_DESCRIPTION_MOISTURE,
                unique_id=SIA_UNIQUE_ID_FORMAT_BINARY.format(
                    entry.entry_id,
                    account_data[CONF_ACCOUNT],
                    zone,
                    ENTITY_DESCRIPTION_MOISTURE.device_class,
                ),
                name=SIA_NAME_FORMAT.format(
                    entry.data[CONF_PORT],
                    account_data[CONF_ACCOUNT],
                    zone,
                    ENTITY_DESCRIPTION_MOISTURE.device_class,
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
        new_state = self.entity_description.code_consequences.get(sia_event.code)
        if new_state is None:
            return False
        _LOGGER.debug("New state will be %s", new_state)
        self._attr_is_on = bool(new_state)
        return True
