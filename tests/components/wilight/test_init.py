"""Tests for the WiLight integration."""
from unittest.mock import patch

import pytest
import pywilight

from homeassistant.components.wilight.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.components.wilight import (
    HOST,
    UPNP_MAC_ADDRESS,
    UPNP_MODEL_NAME_P_B,
    UPNP_MODEL_NUMBER,
    UPNP_SERIAL,
    setup_integration,
)


@pytest.fixture(name="dummy_device_from_host")
def mock_dummy_device_from_host():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_P_B,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


async def test_config_entry_not_ready(hass: HomeAssistantType) -> None:
    """Test the WiLight configuration entry not ready."""
    entry = await setup_integration(hass)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistantType, dummy_device_from_host
) -> None:
    """Test the WiLight configuration entry unloading."""
    entry = await setup_integration(hass)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    if DOMAIN in hass.data:
        assert entry.entry_id not in hass.data[DOMAIN]
        assert entry.state == ENTRY_STATE_NOT_LOADED
