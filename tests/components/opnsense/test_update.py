"""Tests for OPNsense firmware updates."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiopnsense import OPNsenseConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("latest", "expected_state"),
    [("25.7.8", "off"), ("25.7.9", "on")],
)
async def test_firmware_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    latest: str,
    expected_state: str,
) -> None:
    """Test the firmware update entity reports available updates."""
    mock_opnsense_client.get_firmware_update_info.return_value["product"][
        "product_latest"
    ] = latest

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["installed_version"] == "25.7.8"
    assert state.attributes["latest_version"] == latest
    mock_opnsense_client.get_firmware_update_info.assert_awaited_once()


async def test_firmware_update_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test missing data and communication failures make the entity unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_opnsense_client.get_firmware_update_info.return_value = {}
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("update.mock_title_firmware").state == STATE_UNAVAILABLE

    mock_opnsense_client.get_firmware_update_info.side_effect = OPNsenseConnectionError(
        "connection failed"
    )
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("update.mock_title_firmware").state == STATE_UNAVAILABLE
