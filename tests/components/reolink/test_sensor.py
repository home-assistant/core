"""Test the Reolink sensor platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from .conftest import TEST_CAM_NAME, TEST_NVR_NAME

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test sensor entities."""
    reolink_host.ptz_pan_position.return_value = 1200
    reolink_host.wifi_connection.return_value = True
    reolink_host.wifi_signal.return_value = -55
    reolink_host.hdd_list = [0]
    reolink_host.hdd_storage.return_value = 95

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SENSOR}.{TEST_CAM_NAME}_ptz_pan_position"
    assert hass.states.get(entity_id).state == "1200"

    entity_id = f"{Platform.SENSOR}.{TEST_CAM_NAME}_wi_fi_signal"
    assert hass.states.get(entity_id).state == "-55"

    entity_id = f"{Platform.SENSOR}.{TEST_NVR_NAME}_sd_0_storage"
    assert hass.states.get(entity_id).state == "95"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hdd_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test hdd sensor entity."""
    reolink_host.hdd_list = [0]
    reolink_host.hdd_type.return_value = "HDD"
    reolink_host.hdd_storage.return_value = 85
    reolink_host.hdd_available.return_value = False

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SENSOR}.{TEST_NVR_NAME}_hdd_0_storage"
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
