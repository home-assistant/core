"""Tests for the Bosch SHC diagnostics."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from .conftest import smart_plug_device


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Credentials and identifiers are redacted, device data is kept."""
    mock_session.information.macAddress = "aa:bb:cc:dd:ee:ff"
    mock_session.information.shcIpAddress = "1.1.1.1"
    plug = smart_plug_device()
    plug.room_id = "room-1"
    mock_session.devices = [plug]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, "token": "secret", "hostname": "shc-host"},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["entry"]["host"] == REDACTED
    assert diagnostics["entry"]["ssl_certificate"] == REDACTED
    assert diagnostics["entry"]["ssl_key"] == REDACTED
    assert diagnostics["entry"]["token"] == REDACTED
    assert diagnostics["entry"]["hostname"] == REDACTED
    assert diagnostics["entry"]["token"] == REDACTED
    assert diagnostics["entry"]["hostname"] == REDACTED
    assert diagnostics["shc"] == {
        "version": "2.0",
        "update_state": "UP_TO_DATE",
        "macAddress": REDACTED,
        "ip": REDACTED,
    }
    (device,) = diagnostics["devices"]
    assert device["device_id"] == REDACTED
    assert device["root_device_id"] == REDACTED
    assert device["serial"] == REDACTED
    assert device["name"] == "Smart Plug"
    assert device["device_model"] == "PSM"
    assert device["room_id"] == "room-1"
