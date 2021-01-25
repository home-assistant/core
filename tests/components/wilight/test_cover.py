"""Tests for the WiLight integration."""
from unittest.mock import patch

import pytest
import pywilight

from homeassistant.const import STATE_CLOSED
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    HOST,
    UPNP_MAC_ADDRESS,
    UPNP_MODEL_NAME_COVER,
    UPNP_MODEL_NUMBER,
    UPNP_SERIAL,
    WILIGHT_ID,
    setup_integration,
)


@pytest.fixture(name="dummy_device_from_host_cover")
def mock_dummy_device_from_host_light_fan():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_COVER,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


async def test_loading_cover(
    hass: HomeAssistantType,
    dummy_device_from_host_cover,
) -> None:
    """Test the WiLight configuration entry loading."""

    entry = await setup_integration(hass)
    assert entry
    assert entry.unique_id == WILIGHT_ID

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # First segment of the strip
    state = hass.states.get("cover.wl000000000099_1")
    assert state
    assert state.state == STATE_CLOSED

    entry = entity_registry.async_get("cover.wl000000000099_1")
    assert entry
    assert entry.unique_id == "WL000000000099_0"
