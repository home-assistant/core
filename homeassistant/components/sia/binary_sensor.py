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
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ZONES,
    KEY_CONNECTIVITY,
    KEY_MOISTURE,
    KEY_POWER,
    KEY_SMOKE,
    SIA_HUB_ZONE,
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

ENTITY_DESCRIPTION_CONNECTIVITY = SIABinarySensorEntityDescription(
    key=KEY_CONNECTIVITY,
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
    code_consequences={"RP": True},
)


def generate_binary_sensors(entry: ConfigEntry) -> Iterable[SIABinarySensor]:
    """Generate binary sensors.

    For each Account there is one power sensor with zone == 0.
    For each Zone in each Account there is one smoke and one moisture sensor.
    """
    for account_data in entry.data[CONF_ACCOUNTS]:
        account = account_data[CONF_ACCOUNT]
        zones = entry.options[CONF_ACCOUNTS][account][CONF_ZONES]

        yield SIABinarySensorConnectivity(
            entry, account, SIA_HUB_ZONE, ENTITY_DESCRIPTION_CONNECTIVITY
        )
        yield SIABinarySensor(entry, account, SIA_HUB_ZONE, ENTITY_DESCRIPTION_POWER)
        for zone in range(1, zones + 1):
            yield SIABinarySensor(entry, account, zone, ENTITY_DESCRIPTION_SMOKE)
            yield SIABinarySensor(entry, account, zone, ENTITY_DESCRIPTION_MOISTURE)


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
        """Update the state of the binary sensor.

        Return True if the event was relevant for this entity.
        """
        new_state = None
        if sia_event.code:
            new_state = self.entity_description.code_consequences.get(sia_event.code)
        if new_state is None:
            return False
        _LOGGER.debug("New state will be %s", new_state)
        self._attr_is_on = bool(new_state)
        return True


class SIABinarySensorConnectivity(SIABinarySensor):
    """Class for Connectivity Sensor."""

    @callback
    def async_post_interval_update(self, _) -> None:
        """Update state after a ping interval. Overwritten from sia entity base."""
        self._attr_is_on = False
        self.async_write_ha_state()
