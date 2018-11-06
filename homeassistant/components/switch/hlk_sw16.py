"""
Support for HLK-SW16 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.hlk_sw16/
"""
import logging

from homeassistant.components.hlk_sw16 import (
    SwitchableSW16Device, DOMAIN as HLK_SW16,
    DATA_DEVICE_REGISTER)
from homeassistant.components.switch import (
    ToggleEntity)
from homeassistant.const import CONF_NAME

DEPENDENCIES = [HLK_SW16]

_LOGGER = logging.getLogger(__name__)


def devices_from_config(hass, domain_config):
    """Parse configuration and add HLK-SW16 switch devices."""
    device_port = domain_config[0]
    device_config = domain_config[1]
    device_id = domain_config[2]
    device_protocol = hass.data[DATA_DEVICE_REGISTER][device_id]
    device_name = device_config.get(CONF_NAME, device_port)
    device = SW16Switch(device_name, device_port, device_id, device_protocol)
    return [device]


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the HLK-SW16 platform."""
    async_add_entities(devices_from_config(hass, discovery_info))


class SW16Switch(SwitchableSW16Device, ToggleEntity):
    """Representation of a HLK-SW16 switch."""
