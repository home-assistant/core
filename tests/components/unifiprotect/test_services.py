"""Test the UniFi Protect global services."""
# pylint: disable=protected-access
from __future__ import annotations

from pathlib import Path
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyunifiprotect.data import Light
from pyunifiprotect.exceptions import BadRequest

from homeassistant.components.unifiprotect.const import (
    ATTR_ANONYMIZE,
    ATTR_DURATION,
    ATTR_MESSAGE,
    DOMAIN,
    SERVICE_ADD_DOORBELL_TEXT,
    SERVICE_GENERATE_DATA,
    SERVICE_PROFILE_WS,
    SERVICE_REMOVE_DOORBELL_TEXT,
    SERVICE_SET_DEFAULT_DOORBELL_TEXT,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import MockEntityFixture, time_changed


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


@patch("homeassistant.components.unifiprotect.utils.time")
@patch("homeassistant.components.unifiprotect.utils.asyncio")
@patch("homeassistant.components.unifiprotect.utils.json")
@patch("homeassistant.components.unifiprotect.utils.print_ws_stat_summary")
async def test_profile_ws(
    mock_print,
    mock_json,
    mock_asyncio,
    mock_time,
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    mock_entry: MockEntityFixture,
):
    """Test profile_ws service."""

    start = time.monotonic()
    mock_time.time.return_value = time.time()
    mock_time.monotonic.side_effect = [start, start, start + 11]

    mock_asyncio.sleep = AsyncMock()

    mock_stat = Mock()
    mock_stat.__dict__ = {}
    mock_stats = [mock_stat, mock_stat, mock_stat]

    mock_entry.api.bootstrap.capture_ws_stats = False
    mock_entry.api.bootstrap.ws_stats = mock_stats
    mock_entry.api.bootstrap.clear_ws_stats = Mock()

    with patch("builtins.open") as mock_open:
        mock_file = Mock()
        mock_enter = Mock()
        mock_enter.__enter__ = Mock(return_value=mock_file)
        mock_enter.__exit__ = Mock()
        mock_open.return_value = mock_enter

        await hass.services.async_call(
            DOMAIN,
            SERVICE_PROFILE_WS,
            {ATTR_DEVICE_ID: device.id, ATTR_DURATION: 10},
        )
        await time_changed(hass, 15)

        assert mock_entry.api.bootstrap.capture_ws_stats is False
        assert mock_print.called
        assert mock_entry.api.bootstrap.clear_ws_stats.called
        mock_json.dump.assert_called_with([{}, {}, {}], mock_file, indent=4)


async def test_profile_ws_error(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    mock_entry: MockEntityFixture,
):
    """Test profile_ws service, already running."""

    mock_entry.api.bootstrap.capture_ws_stats = True

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PROFILE_WS,
            {ATTR_DEVICE_ID: device.id, ATTR_DURATION: 10},
            blocking=True,
        )


@patch("homeassistant.components.unifiprotect.utils.time")
@patch("homeassistant.components.unifiprotect.utils.shutil")
@patch("homeassistant.components.unifiprotect.utils.SampleDataGenerator")
async def test_generate_data(
    mock_data,
    mock_shutil,
    mock_time,
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    mock_entry: MockEntityFixture,
):
    """Test generate_data service."""

    now = time.time()
    mock_time.time.return_value = now

    mock_generate = Mock()
    mock_generate.async_generate = AsyncMock()
    mock_data.return_value = mock_generate

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GENERATE_DATA,
        {ATTR_DEVICE_ID: device.id, ATTR_DURATION: 10, ATTR_ANONYMIZE: False},
        blocking=True,
    )

    hass_path = hass.config.path(f"ufp_sample.{now}")
    mock_data.assert_called_with(mock_entry.api, Path(hass_path), False, 10)
    mock_generate.async_generate.assert_called_once_with(close_session=False)
    mock_shutil.make_archive.assert_called_once_with(hass_path, "zip", hass_path)
    mock_shutil.rmtree.assert_called_once_with(hass_path)
