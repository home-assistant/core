"""Tests for 1-Wire devices connected on OWServer."""
import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
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
    with patch("homeassistant.components.onewire.PLATFORMS", [BINARY_SENSOR_DOMAIN]):
        yield


async def test_owserver_binary_sensor(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    caplog: pytest.LogCaptureFixture,
):
    """Test for 1-Wire binary sensor.

    This test forces all entities to be enabled.
    """
    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(BINARY_SENSOR_DOMAIN, [])
    expected_devices = ensure_list(mock_device.get(ATTR_DEVICE_INFO))

    setup_owproxy_mock_devices(owproxy, BINARY_SENSOR_DOMAIN, [device_id])
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

    setup_owproxy_mock_devices(owproxy, BINARY_SENSOR_DOMAIN, [device_id])
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities(hass, entity_registry, expected_entities)
