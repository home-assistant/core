"""Test the OpenGarage Browser buttons."""

import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.components import button
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_buttons(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test standard OpenGarage buttons."""
    entry = entity_registry.async_get("button.garage_abcdef_restart")
    assert entry
    assert entry.unique_id == "12345_restart"
    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.garage_abcdef_restart"},
        blocking=True,
    )
    assert len(mock_opengarage.reboot.mock_calls) == 1

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry


async def test_device_info_sw_version_is_string(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that sw_version is a string even when API returns int."""
    mock_config_entry.add_to_hass(hass)
    with caplog.at_level(logging.WARNING, logger="homeassistant.helpers.frame"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}
    )
    assert device_entry
    assert device_entry.sw_version == "120"
    assert "non-string value" not in caplog.text
