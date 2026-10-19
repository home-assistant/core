"""Support for Rflink switches."""

import probatio

from homeassistant.components.switch import (
    DOMAIN as PLATFORM_DOMAIN,
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
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
from .utils import create_issue_yaml_migration

PARALLEL_UPDATES = 0

RFLINK_PLATFORM = {
    probatio.Optional(
        CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})
    ): DEVICE_DEFAULTS_SCHEMA,
    probatio.Optional(CONF_DEVICES, default={}): {
        cv.string: probatio.Schema(
            {
                probatio.Optional(CONF_NAME): cv.string,
                probatio.Optional(CONF_ALIASES, default=[]): probatio.All(
                    cv.ensure_list, [cv.string]
                ),
                probatio.Optional(CONF_GROUP_ALIASES, default=[]): probatio.All(
                    cv.ensure_list, [cv.string]
                ),
                probatio.Optional(CONF_NOGROUP_ALIASES, default=[]): probatio.All(
                    cv.ensure_list, [cv.string]
                ),
                probatio.Optional(CONF_FIRE_EVENT): cv.boolean,
                probatio.Optional(CONF_SIGNAL_REPETITIONS): probatio.Coerce(int),
                probatio.Optional(CONF_GROUP, default=True): cv.boolean,
            }
        )
    },
}

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    RFLINK_PLATFORM,
    extra=probatio.ALLOW_EXTRA,
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
    if discovery_info is None:
        create_issue_yaml_migration(hass, PLATFORM_DOMAIN)
        async_add_entities(devices_from_config(config))
    else:
        async_add_entities(devices_from_config(discovery_info))


class RflinkSwitch(SwitchableRflinkDevice, SwitchEntity):
    """Representation of a Rflink switch."""
