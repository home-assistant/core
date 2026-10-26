"""Tests for Zentraly device information refresh actions."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from zentraly import ZentralyConnectionError, ZentralyDeviceInfo

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import DEVICE_ID

pytestmark = pytest.mark.usefixtures("setup_integration")


async def test_refresh_device_information(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The diagnostic action refreshes versions on the existing physical device."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{DEVICE_ID}_refresh_device_info"
    )
    entity = entity_registry.async_get(entity_id)
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    mock_device_info.reset_mock()
    mock_device_info.return_value = ZentralyDeviceInfo("1.1", "2.1")
    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_device_info.assert_awaited_once_with()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert device.sw_version == "1.1"
    assert device.hw_version == "2.1"
    assert entity.device_id == device.id


async def test_refresh_failure(
    hass: HomeAssistant,
    mock_device_info: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Manual failures are translated instead of reporting a successful refresh."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{DEVICE_ID}_refresh_device_info"
    )
    mock_device_info.side_effect = ZentralyConnectionError
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert error.value.translation_key == "cannot_connect"


@pytest.mark.parametrize(
    ("info", "error_key", "firmware", "hardware"),
    [
        pytest.param(
            ZentralyDeviceInfo(None, "2.1"),
            "firmware_read_failed",
            "1.0",
            "2.1",
            id="firmware",
        ),
        pytest.param(
            ZentralyDeviceInfo("1.1", None),
            "hardware_read_failed",
            "1.1",
            "2.0",
            id="hardware",
        ),
        pytest.param(
            ZentralyDeviceInfo(), "versions_read_failed", "1.0", "2.0", id="both"
        ),
        pytest.param(
            ZentralyDeviceInfo(None, "2.0"),
            "firmware_read_failed",
            "1.0",
            "2.0",
            id="unchanged-hardware",
        ),
    ],
)
async def test_incomplete_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    info: ZentralyDeviceInfo,
    error_key: str,
    firmware: str,
    hardware: str,
) -> None:
    """Report failed fields while retaining cached and successfully read versions."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{DEVICE_ID}_refresh_device_info"
    )
    mock_device_info.return_value = info
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == error_key
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert device.sw_version == firmware
    assert device.hw_version == hardware


async def test_disconnect_while_press_waits(
    hass: HomeAssistant,
    mock_device_info: AsyncMock,
    entity_registry: er.EntityRegistry,
    connection_state: Callable[[bool], None],
) -> None:
    """A press accepted before disconnection fails when its queued read starts."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def read() -> ZentralyDeviceInfo:
        started.set()
        await release.wait()
        return ZentralyDeviceInfo("1.1", "2.1")

    mock_device_info.reset_mock()
    mock_device_info.side_effect = read
    entity_id = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{DEVICE_ID}_refresh_device_info"
    )
    first = hass.async_create_task(
        hass.services.async_call(
            BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    )
    await started.wait()
    second = hass.async_create_task(
        hass.services.async_call(
            BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    )
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not second.done()
        connection_state(False)
    finally:
        release.set()
        await first
    with pytest.raises(HomeAssistantError) as error:
        await second
    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "cannot_connect"
    mock_device_info.assert_awaited_once_with()
