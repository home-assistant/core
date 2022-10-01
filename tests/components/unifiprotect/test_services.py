"""Test the UniFi Protect global services."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera, Chime, Light, ModelType
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

from .utils import MockUFPFixture, init_entry


@pytest.fixture(name="device")
async def device_fixture(hass: HomeAssistant, ufp: MockUFPFixture):
    """Fixture with entry setup to call services with."""

    await init_entry(hass, ufp, [])

    device_registry = dr.async_get(hass)

    return list(device_registry.devices.values())[0]


@pytest.fixture(name="subdevice")
async def subdevice_fixture(hass: HomeAssistant, ufp: MockUFPFixture, light: Light):
    """Fixture with entry setup to call services with."""

    await init_entry(hass, ufp, [light])

    device_registry = dr.async_get(hass)

    return [d for d in device_registry.devices.values() if d.name != "UnifiProtect"][0]


async def test_global_service_bad_device(hass: HomeAssistant, ufp: MockUFPFixture):
    """Test global service, invalid device ID."""

    nvr = ufp.api.bootstrap.nvr
    nvr.__fields__["add_custom_doorbell_message"] = Mock(final=False)
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
    hass: HomeAssistant, device: dr.DeviceEntry, ufp: MockUFPFixture
):
    """Test global service, unexpected error."""

    nvr = ufp.api.bootstrap.nvr
    nvr.__fields__["add_custom_doorbell_message"] = Mock(final=False)
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
    hass: HomeAssistant, device: dr.DeviceEntry, ufp: MockUFPFixture
):
    """Test add_doorbell_text service."""

    nvr = ufp.api.bootstrap.nvr
    nvr.__fields__["add_custom_doorbell_message"] = Mock(final=False)
    nvr.add_custom_doorbell_message = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_DOORBELL_TEXT,
        {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
        blocking=True,
    )
    nvr.add_custom_doorbell_message.assert_called_once_with("Test Message")


async def test_remove_doorbell_text(
    hass: HomeAssistant, subdevice: dr.DeviceEntry, ufp: MockUFPFixture
):
    """Test remove_doorbell_text service."""

    nvr = ufp.api.bootstrap.nvr
    nvr.__fields__["remove_custom_doorbell_message"] = Mock(final=False)
    nvr.remove_custom_doorbell_message = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_DOORBELL_TEXT,
        {ATTR_DEVICE_ID: subdevice.id, ATTR_MESSAGE: "Test Message"},
        blocking=True,
    )
    nvr.remove_custom_doorbell_message.assert_called_once_with("Test Message")


async def test_set_default_doorbell_text(
    hass: HomeAssistant, device: dr.DeviceEntry, ufp: MockUFPFixture
):
    """Test set_default_doorbell_text service."""

    nvr = ufp.api.bootstrap.nvr
    nvr.__fields__["set_default_doorbell_message"] = Mock(final=False)
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
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
):
    """Test set_chime_paired_doorbells."""

    ufp.api.update_device = AsyncMock()

    camera1 = doorbell.copy()
    camera1.name = "Test Camera 1"

    camera2 = doorbell.copy()
    camera2.name = "Test Camera 2"

    await init_entry(hass, ufp, [camera1, camera2, chime])

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

    ufp.api.update_device.assert_called_once_with(
        ModelType.CHIME, chime.id, {"cameraIds": sorted([camera1.id, camera2.id])}
    )
