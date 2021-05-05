"""Support for 1-Wire environment switches."""
import logging
import os

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_TYPE

from .const import CONF_TYPE_OWSERVER, DOMAIN, SWITCH_TYPE_LATCH, SWITCH_TYPE_PIO
from .onewire_entities import OneWireProxyEntity
from .onewirehub import OneWireHub

DEVICE_SWITCHES = {
    # Family : { owfs path }
    "05": [
        {
            "path": "PIO",
            "name": "PIO",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
    ],
    "12": [
        {
            "path": "PIO.A",
            "name": "PIO A",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.B",
            "name": "PIO B",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "latch.A",
            "name": "Latch A",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.B",
            "name": "Latch B",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
    ],
    "29": [
        {
            "path": "PIO.0",
            "name": "PIO 0",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.1",
            "name": "PIO 1",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.2",
            "name": "PIO 2",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.3",
            "name": "PIO 3",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.4",
            "name": "PIO 4",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.5",
            "name": "PIO 5",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.6",
            "name": "PIO 6",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "PIO.7",
            "name": "PIO 7",
            "type": SWITCH_TYPE_PIO,
            "default_disabled": True,
        },
        {
            "path": "latch.0",
            "name": "Latch 0",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.1",
            "name": "Latch 1",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.2",
            "name": "Latch 2",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.3",
            "name": "Latch 3",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.4",
            "name": "Latch 4",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.5",
            "name": "Latch 5",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.6",
            "name": "Latch 6",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
        {
            "path": "latch.7",
            "name": "Latch 7",
            "type": SWITCH_TYPE_LATCH,
            "default_disabled": True,
        },
    ],
}

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up 1-Wire platform."""
    # Only OWServer implementation works with switches
    if config_entry.data[CONF_TYPE] == CONF_TYPE_OWSERVER:
        onewirehub = hass.data[DOMAIN][config_entry.unique_id]

        entities = await hass.async_add_executor_job(get_entities, onewirehub)
        async_add_entities(entities, True)


def get_entities(onewirehub: OneWireHub):
    """Get a list of entities."""
    entities = []

    for device in onewirehub.devices:
        family = device["family"]
        device_type = device["type"]
        device_id = os.path.split(os.path.split(device["path"])[0])[1]

        if family not in DEVICE_SWITCHES:
            continue

        device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Maxim Integrated",
            "model": device_type,
            "name": device_id,
        }
        for entity_specs in DEVICE_SWITCHES[family]:
            entity_path = os.path.join(
                os.path.split(device["path"])[0], entity_specs["path"]
            )
            entities.append(
                OneWireProxySwitch(
                    device_id=device_id,
                    device_name=device_id,
                    device_info=device_info,
                    entity_path=entity_path,
                    entity_specs=entity_specs,
                    owproxy=onewirehub.owproxy,
                )
            )

    return entities


class OneWireProxySwitch(OneWireProxyEntity, SwitchEntity):
    """Implementation of a 1-Wire switch."""

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self._write_value_ownet(b"1")

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self._write_value_ownet(b"0")
