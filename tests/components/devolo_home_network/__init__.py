"""Tests for the devolo Home Network integration."""

import dataclasses
from typing import Any

from devolo_plc_api.device_api.deviceapi import DeviceApi
from devolo_plc_api.plcnet_api.plcnetapi import PlcNetApi

from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .const import DISCOVERY_INFO, IP

from tests.common import MockConfigEntry


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        CONF_IP_ADDRESS: IP,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    return entry


async def async_connect(self, session_instance: Any = None):
    """Give a mocked device the needed properties."""
    self.plcnet = PlcNetApi(IP, None, dataclasses.asdict(DISCOVERY_INFO))
    self.device = DeviceApi(IP, None, dataclasses.asdict(DISCOVERY_INFO))
    self.mac = DISCOVERY_INFO.properties["PlcMacAddress"]
    self.product = DISCOVERY_INFO.properties["Product"]
    self.serial_number = DISCOVERY_INFO.properties["SN"]
