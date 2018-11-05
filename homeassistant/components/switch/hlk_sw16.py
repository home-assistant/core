"""
Support for HLK-SW16 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.hlk_sw16/
"""
import logging

from homeassistant.components.hlk_sw16 import (
    SwitchableSW16Device, DOMAIN as HLK_SW16)
from homeassistant.components.switch import (
    ToggleEntity)
from homeassistant.const import CONF_NAME

DEPENDENCIES = [HLK_SW16]

_LOGGER = logging.getLogger(__name__)


def devices_from_config(domain_config):
    """Parse configuration and add HLK-SW16 switch devices."""
    devices = []
    for device_port, device_name in domain_config[HLK_SW16]:
        device = SW16Switch(device_name.get(CONF_NAME, device_port),
                            device_port)
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the HLK-SW16 platform."""
    async_add_entities(devices_from_config(discovery_info),
                       update_before_add=True)


class SW16Switch(SwitchableSW16Device, ToggleEntity):
    """Representation of a HLK-SW16 switch."""

    @property
    def force_update(self) -> bool:
        """Will trigger anytime the state property is updated."""
        return True
