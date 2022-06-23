"""Tests for 1-Wire sensors."""
import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import ensure_list

from . import (
    check_and_enable_disabled_entities,
    check_device_registry,
    check_entities,
    setup_owproxy_mock_devices,
)
from .const import ATTR_DEVICE_INFO, ATTR_UNKNOWN_DEVICE, MOCK_OWPROXY_DEVICES

from tests.common import mock_device_registry, mock_registry


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    caplog: pytest.LogCaptureFixture,
):
    """Test for 1-Wire device.

    As they would be on a clean setup: all binary-sensors and switches disabled.
    """
    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(Platform.SENSOR, [])
    if "branches" in mock_device:
        for branch_details in mock_device["branches"].values():
            for sub_device in branch_details.values():
                expected_entities += sub_device[Platform.SENSOR]
    expected_devices = ensure_list(mock_device.get(ATTR_DEVICE_INFO))

    setup_owproxy_mock_devices(owproxy, Platform.SENSOR, [device_id])
    with caplog.at_level(logging.WARNING, logger="homeassistant.components.onewire"):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        if mock_device.get(ATTR_UNKNOWN_DEVICE):
            assert "Ignoring unknown device family/type" in caplog.text
        else:
            assert "Ignoring unknown device family/type" not in caplog.text

    check_device_registry(device_registry, expected_devices)
    assert len(entity_registry.entities) == len(expected_entities)
    check_and_enable_disabled_entities(entity_registry, expected_entities)

    setup_owproxy_mock_devices(owproxy, Platform.SENSOR, [device_id])
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities(hass, entity_registry, expected_entities)
