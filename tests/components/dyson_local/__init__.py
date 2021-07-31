"""Tests for Dyson Local."""

from typing import Type
from unittest.mock import MagicMock, patch

from libdyson import DysonDevice, MessageType

from homeassistant.components.dyson_local import DOMAIN
from homeassistant.components.dyson_local.const import (
    CONF_CREDENTIAL,
    CONF_DEVICE_TYPE,
    CONF_SERIAL,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback

from tests.common import MockConfigEntry

HOST = "192.168.1.10"
SERIAL = "JH1-US-HBB1111A"
CREDENTIAL = "aoWJM1kpL79MN2dPMlL5ysQv/APG+HAv+x3HDk0yuT3gMfgA3mLuil4O3d+q6CcyU+D1Hoir38soKoZHshYFeQ=="
NAME = "name"

MODULE = "homeassistant.components.dyson_local"


def get_base_device(spec: Type[DysonDevice], device_type: str) -> DysonDevice:
    """Get mocked device with common properties."""
    device = MagicMock(spec=spec)
    device.serial = SERIAL
    device.device_type = device_type
    return device


async def setup_entry(hass: HomeAssistant, device: DysonDevice):
    """Set up mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL: SERIAL,
            CONF_CREDENTIAL: CREDENTIAL,
            CONF_HOST: HOST,
            CONF_DEVICE_TYPE: device.device_type,
            CONF_NAME: NAME,
        },
    )
    config_entry.add_to_hass(hass)
    with patch(f"{MODULE}.get_device", return_value=device):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def update_device(
    hass: HomeAssistant, device: DysonDevice, message_type: MessageType
) -> None:
    """Update device status."""
    listeners = [call[0][0] for call in device.add_message_listener.call_args_list]
    for listener in listeners:
        await hass.async_add_executor_job(listener, message_type)
    await hass.async_block_till_done()


@callback
def name_to_entity(name: str):
    """Transform entity name to entity id."""
    return name.lower().replace(" ", "_")
