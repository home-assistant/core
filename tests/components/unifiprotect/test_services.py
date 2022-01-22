"""Test the UniFi Protect global services."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Light
from pyunifiprotect.exceptions import BadRequest

from homeassistant.components.unifiprotect.const import ATTR_MESSAGE, DOMAIN
from homeassistant.components.unifiprotect.services import (
    SERVICE_ADD_DOORBELL_TEXT,
    SERVICE_REMOVE_DOORBELL_TEXT,
    SERVICE_SET_DEFAULT_DOORBELL_TEXT,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import MockEntityFixture


@pytest.fixture(name="device")
async def device_fixture(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Fixture with entry setup to call services with."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    device_registry = await dr.async_get_registry(hass)

    return list(device_registry.devices.values())[0]


@pytest.fixture(name="subdevice")
async def subdevice_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Fixture with entry setup to call services with."""

    mock_light._api = mock_entry.api
    mock_entry.api.bootstrap.lights = {
        mock_light.id: mock_light,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    device_registry = await dr.async_get_registry(hass)

    return [d for d in device_registry.devices.values() if d.name != "UnifiProtect"][0]


async def test_global_service_bad_device(
    hass: HomeAssistant, device: dr.DeviceEntry, mock_entry: MockEntityFixture
):
    """Test global service, invalid device ID."""

    nvr = mock_entry.api.bootstrap.nvr
    nvr.__fields__["add_custom_doorbell_message"] = Mock()
    nvr.add_custom_doorbell_message = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_DOORBELL_TEXT,
            {ATTR_DEVICE_ID: "bad_device_id", ATTR_MESSAGE: "Test Message"},
            blocking=True,
        )
    assert not nvr.add_custom_doorbell_message.called


async def test_global_service_exception(
    hass: HomeAssistant, device: dr.DeviceEntry, mock_entry: MockEntityFixture
):
    """Test global service, unexpected error."""

    nvr = mock_entry.api.bootstrap.nvr
    nvr.__fields__["add_custom_doorbell_message"] = Mock()
    nvr.add_custom_doorbell_message = AsyncMock(side_effect=BadRequest)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_DOORBELL_TEXT,
            {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
            blocking=True,
        )
    assert nvr.add_custom_doorbell_message.called


async def test_add_doorbell_text(
    hass: HomeAssistant, device: dr.DeviceEntry, mock_entry: MockEntityFixture
):
    """Test add_doorbell_text service."""

    nvr = mock_entry.api.bootstrap.nvr
    nvr.__fields__["add_custom_doorbell_message"] = Mock()
    nvr.add_custom_doorbell_message = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_DOORBELL_TEXT,
        {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
        blocking=True,
    )
    nvr.add_custom_doorbell_message.assert_called_once_with("Test Message")


async def test_remove_doorbell_text(
    hass: HomeAssistant, subdevice: dr.DeviceEntry, mock_entry: MockEntityFixture
):
    """Test remove_doorbell_text service."""

    nvr = mock_entry.api.bootstrap.nvr
    nvr.__fields__["remove_custom_doorbell_message"] = Mock()
    nvr.remove_custom_doorbell_message = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_DOORBELL_TEXT,
        {ATTR_DEVICE_ID: subdevice.id, ATTR_MESSAGE: "Test Message"},
        blocking=True,
    )
    nvr.remove_custom_doorbell_message.assert_called_once_with("Test Message")


async def test_set_default_doorbell_text(
    hass: HomeAssistant, device: dr.DeviceEntry, mock_entry: MockEntityFixture
):
    """Test set_default_doorbell_text service."""

    nvr = mock_entry.api.bootstrap.nvr
    nvr.__fields__["set_default_doorbell_message"] = Mock()
    nvr.set_default_doorbell_message = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEFAULT_DOORBELL_TEXT,
        {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
        blocking=True,
    )
    nvr.set_default_doorbell_message.assert_called_once_with("Test Message")
