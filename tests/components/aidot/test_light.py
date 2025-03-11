"""Test the aidot device."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aidot.const import CONF_ID, CONF_MAC, CONF_NAME
from syrupy import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
)
from homeassistant.components.sensor import timedelta
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    ENTITY_LIGHT,
    LIGHT_DOMAIN,
    TEST_DEVICE_LIST,
    TEST_MULTI_DEVICE_LIST,
    DeviceClient,
    DeviceInformation,
    DeviceStatusData,
)

from tests.common import Mock, MockConfigEntry, snapshot_platform


def mocked_add_device_client(device: dict[str, Any]) -> MagicMock:
    """Fixture DeviceClient."""
    mock_device_client = MagicMock(spec=DeviceClient)
    mock_device_client.device_id = device.get(CONF_ID)

    mock_info = Mock(spec=DeviceInformation)
    mock_info.enable_rgbw = True
    mock_info.enable_dimming = True
    mock_info.enable_cct = True
    mock_info.cct_min = 2700
    mock_info.cct_max = 6500
    mock_info.dev_id = device.get(CONF_ID)
    mock_info.mac = device.get(CONF_MAC)
    mock_info.model_id = "aidot.light.rgbw"
    mock_info.name = device.get(CONF_NAME)
    mock_info.hw_version = "1.0"
    mock_device_client.info = mock_info

    status = Mock(spec=DeviceStatusData)
    status.online = True
    status.dimming = 255
    status.cct = 3000
    status.on = True
    status.rgbw = (255, 255, 255, 255)
    mock_device_client.status = status
    mock_device_client.read_status = AsyncMock(return_value=status)
    return mock_device_client


async def test_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_device_client.async_turn_on.assert_called_once()


async def test_turn_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn off."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_device_client.async_turn_off.assert_called_once()


async def test_trun_on_brightness(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on brightness."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    mocked_device_client.async_set_brightness.assert_called_once()


async def test_turn_on_with_color_temp(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on with color temp."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )
    mocked_device_client.async_set_cct.assert_called_once()


async def test_turn_on_with_rgbw(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on with rgbw."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    mocked_device_client.async_set_rgbw.assert_called_once()


async def test_dynamic_device_add(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_aidot_client
) -> None:
    """Test if adding a new device dynamically creates the corresponding light entity."""

    with patch(
        "homeassistant.components.aidot.coordinator.UPDATE_DEVICE_LIST_INTERVAL",
        timedelta(seconds=1),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(dr.async_get(hass).devices) == 1

        @callback
        def get_device_client(device: dict[str, Any]):
            return mocked_add_device_client(device)

        mocked_aidot_client.get_device_client = get_device_client
        mocked_aidot_client.async_get_all_device = AsyncMock(
            return_value=TEST_MULTI_DEVICE_LIST
        )
        await asyncio.sleep(2)
        assert len(dr.async_get(hass).devices) == 2


async def test_dynamic_device_remove(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_aidot_client
) -> None:
    """Test if adding a new device dynamically creates the corresponding light entity."""

    @callback
    def get_device_client(device: dict[str, Any]):
        return mocked_add_device_client(device)

    mocked_aidot_client.get_device_client = get_device_client
    mocked_aidot_client.async_get_all_device = AsyncMock(
        return_value=TEST_MULTI_DEVICE_LIST
    )
    with patch(
        "homeassistant.components.aidot.coordinator.UPDATE_DEVICE_LIST_INTERVAL",
        timedelta(seconds=1),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(dr.async_get(hass).devices) == 2
        mocked_aidot_client.async_get_all_device = AsyncMock(
            return_value=TEST_DEVICE_LIST
        )
        await asyncio.sleep(2)
        assert len(dr.async_get(hass).devices) == 1
