"""Tests for the Insteon lock."""
from asyncio import sleep
from unittest.mock import patch

from pyinsteon.config import NON_TOGGLE_MASK, NON_TOGGLE_ON_OFF_MASK, TOGGLE_BUTTON
from pyinsteon.constants import ToggleMode
import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon import (
    DOMAIN,
    insteon_entity,
    utils as insteon_utils,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry

devices = MockDevices()


@pytest.fixture(autouse=True)
def number_platform_only():
    """Only setup the number and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.insteon.INSTEON_PLATFORMS",
        (Platform.SELECT,),
    ):
        yield


@pytest.fixture(autouse=True)
def patch_setup_and_devices():
    """Patch the Insteon setup process and devices."""
    with patch.object(insteon, "async_connect", new=mock_connection), patch.object(
        insteon, "async_close"
    ), patch.object(insteon, "devices", devices), patch.object(
        insteon_utils, "devices", devices
    ), patch.object(
        insteon_entity, "devices", devices
    ), patch(
        "homeassistant.components.insteon.insteon_entity.WRITE_DELAY",
        1,
    ):
        yield


async def mock_connection(*args, **kwargs):
    """Return a successful connection."""
    return True


async def test_number_config_updates(hass: HomeAssistant) -> None:
    """Test updating an Insteon number configuration entity."""

    await devices.async_load()
    device = devices["33.33.33"]
    device.properties[NON_TOGGLE_MASK].load(0)
    device.properties[NON_TOGGLE_ON_OFF_MASK].load(0)

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)
    registry_entity = er.async_get(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    try:
        select = registry_entity.async_get(
            "select.device_33_33_33_33_33_33_toggle_button_b"
        )
        state = hass.states.get(select.entity_id)
        assert state.state == "toggle"

        # set value via UI
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {"entity_id": select.entity_id, "option": "on_only"},
            blocking=True,
        )
        assert (
            device.configuration[f"{TOGGLE_BUTTON}_b"].new_value == ToggleMode.ON_ONLY
        )
        await sleep(1)
        assert device.async_write_config.call_count == 1
    finally:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
