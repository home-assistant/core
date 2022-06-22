"""Test the UniFi Protect global services."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera, Chime, Light, ModelType
from pyunifiprotect.data.bootstrap import ProtectDeviceRef
from pyunifiprotect.exceptions import BadRequest

from homeassistant.components.unifiprotect.const import ATTR_MESSAGE, DOMAIN
from homeassistant.components.unifiprotect.services import (
    SERVICE_ADD_DOORBELL_TEXT,
    SERVICE_REMOVE_DOORBELL_TEXT,
    SERVICE_SET_CHIME_PAIRED,
    SERVICE_SET_DEFAULT_DOORBELL_TEXT,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockEntityFixture, regenerate_device_ids


@pytest.fixture(name="device")
async def device_fixture(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Fixture with entry setup to call services with."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

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

    device_registry = dr.async_get(hass)

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


async def test_set_chime_paired_doorbells(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_chime: Chime,
    mock_camera: Camera,
):
    """Test set_chime_paired_doorbells."""

    mock_entry.api.update_device = AsyncMock()

    mock_chime._api = mock_entry.api
    mock_chime.name = "Test Chime"
    mock_chime._initial_data = mock_chime.dict()
    mock_entry.api.bootstrap.chimes = {
        mock_chime.id: mock_chime,
    }
    mock_entry.api.bootstrap.mac_lookup = {
        mock_chime.mac.lower(): ProtectDeviceRef(
            model=mock_chime.model, id=mock_chime.id
        )
    }

    camera1 = mock_camera.copy()
    camera1.name = "Test Camera 1"
    camera1._api = mock_entry.api
    camera1.channels[0]._api = mock_entry.api
    camera1.channels[1]._api = mock_entry.api
    camera1.channels[2]._api = mock_entry.api
    camera1.feature_flags.has_chime = True
    regenerate_device_ids(camera1)

    camera2 = mock_camera.copy()
    camera2.name = "Test Camera 2"
    camera2._api = mock_entry.api
    camera2.channels[0]._api = mock_entry.api
    camera2.channels[1]._api = mock_entry.api
    camera2.channels[2]._api = mock_entry.api
    camera2.feature_flags.has_chime = True
    regenerate_device_ids(camera2)

    mock_entry.api.bootstrap.cameras = {
        camera1.id: camera1,
        camera2.id: camera2,
    }
    mock_entry.api.bootstrap.mac_lookup[camera1.mac.lower()] = ProtectDeviceRef(
        model=camera1.model, id=camera1.id
    )
    mock_entry.api.bootstrap.mac_lookup[camera2.mac.lower()] = ProtectDeviceRef(
        model=camera2.model, id=camera2.id
    )

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    chime_entry = registry.async_get("button.test_chime_play_chime")
    camera_entry = registry.async_get("binary_sensor.test_camera_2_doorbell")
    assert chime_entry is not None
    assert camera_entry is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CHIME_PAIRED,
        {
            ATTR_DEVICE_ID: chime_entry.device_id,
            "doorbells": {
                ATTR_ENTITY_ID: ["binary_sensor.test_camera_1_doorbell"],
                ATTR_DEVICE_ID: [camera_entry.device_id],
            },
        },
        blocking=True,
    )

    mock_entry.api.update_device.assert_called_once_with(
        ModelType.CHIME, mock_chime.id, {"cameraIds": sorted([camera1.id, camera2.id])}
    )
