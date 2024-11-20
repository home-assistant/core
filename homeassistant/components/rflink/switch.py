"""Support for Rflink switches."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ALIASES,
    CONF_DEVICE_DEFAULTS,
    CONF_FIRE_EVENT,
    CONF_GROUP,
    CONF_GROUP_ALIASES,
    CONF_NOGROUP_ALIASES,
    CONF_SIGNAL_REPETITIONS,
    DEVICE_DEFAULTS_SCHEMA,
)
from .entity import SwitchableRflinkDevice

PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})
        ): DEVICE_DEFAULTS_SCHEMA,
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_GROUP_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_NOGROUP_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_FIRE_EVENT): cv.boolean,
                    vol.Optional(CONF_SIGNAL_REPETITIONS): vol.Coerce(int),
                    vol.Optional(CONF_GROUP, default=True): cv.boolean,
                }
            )
        },
    },
    extra=vol.ALLOW_EXTRA,
)


def devices_from_config(domain_config):
    """Parse configuration and add Rflink switch devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)
        device = RflinkSwitch(device_id, **device_config)
        devices.append(device)

    return devices


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config))


class RflinkSwitch(SwitchableRflinkDevice, SwitchEntity):
    """Representation of a Rflink switch."""
