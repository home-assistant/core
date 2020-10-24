"""Test the Panasonic Viera remote entity."""

from homeassistant.components.panasonic_viera.const import ATTR_UDN, DOMAIN
from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON

from .test_init import (
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_INFO,
    MOCK_ENCRYPTION_DATA,
    get_mock_remote,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def setup_panasonic_viera(hass):
    """Initialize integration for tests."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA, **MOCK_DEVICE_INFO},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()


async def test_turn_on(hass):
    """Test turn on service call."""
    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await setup_panasonic_viera(hass)

        data = {ATTR_ENTITY_ID: "remote.panasonic_viera_tv"}
        await hass.services.async_call(REMOTE_DOMAIN, SERVICE_TURN_ON, data)
        await hass.async_block_till_done()


async def test_turn_off(hass):
    """Test turn off service call."""
    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await setup_panasonic_viera(hass)

        data = {ATTR_ENTITY_ID: "remote.panasonic_viera_tv"}
        await hass.services.async_call(REMOTE_DOMAIN, SERVICE_TURN_OFF, data)
        await hass.async_block_till_done()


async def test_send_command(hass):
    """Test send command service call."""
    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await setup_panasonic_viera(hass)

        data = {ATTR_ENTITY_ID: "remote.panasonic_viera_tv", ATTR_COMMAND: "power"}
        await hass.services.async_call(REMOTE_DOMAIN, SERVICE_SEND_COMMAND, data)
        await hass.async_block_till_done()
