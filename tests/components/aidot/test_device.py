"""Test the aidot device."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTITY_LIGHT = "light.test_light"
LIGHT_DOMAIN = "light"


@pytest.fixture(name="device", autouse=True)
def device_fixture():
    """Device fixture."""
    with (
        patch(
            "homeassistant.components.aidot.coordinator.AidotDeviceUpdateCoordinator._async_update_data",
            return_value=_mocked_status(),
        ),
        patch(
            "homeassistant.components.aidot.coordinator.AidotDeviceUpdateCoordinator._async_setup",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aidot.coordinator.AidotDeviceManagerCoordinator",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aidot.coordinator.AidotClient.start_discover",
            new=Mock(),
        ),
        patch(
            "homeassistant.components.aidot.coordinator.AidotClient.async_get_all_device",
            return_value=mock_device_list(),
        ),
        patch(
            "homeassistant.components.aidot.__init__.AidotDeviceManagerCoordinator.cleanup",
            return_value=mock_device_list(),
        ),
        patch(
            "homeassistant.components.aidot.coordinator.DeviceClient.ping_task",
            return_value=AsyncMock(),
        ),
    ):
        yield


def mock_device_list():
    """Fixture for a mock device."""
    return {
        "device_list": [
            {
                "id": "device_id",
                "name": "Test Light",
                "modelId": "aidot.light.rgbw",
                "mac": "AA:BB:CC:DD:EE:FF",
                "hardwareVersion": "1.0",
                "type": "light",
                "aesKey": ["mock_aes_key"],
                "product": {
                    "id": "test_product",
                    "serviceModules": [
                        {"identity": "control.light.rgbw"},
                        {
                            "identity": "control.light.cct",
                            "properties": [
                                {"identity": "CCT", "maxValue": 6500, "minValue": 2700}
                            ],
                        },
                    ],
                },
            }
        ]
    }


def _mocked_status():
    status = Mock()
    status.online = True
    status.brightness = 255
    status.cct = 3000
    status.on = True
    status.rgbw = (255, 255, 255, 255)
    return status


async def test_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON


async def test_min_color_temp_kelvin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test min cct."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).attributes["min_color_temp_kelvin"] == 2700


async def test_max_color_temp_kelvin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test max cct."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_LIGHT).attributes["max_color_temp_kelvin"] == 6500


async def test_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    with patch(
        "homeassistant.components.aidot.coordinator.DeviceClient.async_turn_on",
        new_callable=AsyncMock,
    ) as mock_async_call:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT},
            blocking=True,
        )
        mock_async_call.assert_called_once()


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn off."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    with patch(
        "homeassistant.components.aidot.coordinator.DeviceClient.async_turn_off",
        new_callable=AsyncMock,
    ) as mock_async_call:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_LIGHT},
            blocking=True,
        )
        mock_async_call.assert_called_once()


async def test_trun_on_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on brightness."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    with patch(
        "homeassistant.components.aidot.coordinator.DeviceClient.async_set_brightness",
        new_callable=AsyncMock,
    ) as mock_async_call:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 100},
            blocking=True,
        )
        mock_async_call.assert_called_once()


async def test_turn_on_with_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on with color temp."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    with patch(
        "homeassistant.components.aidot.coordinator.DeviceClient.async_set_cct",
        new_callable=AsyncMock,
    ) as mock_async_call:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 3000},
            blocking=True,
        )
        mock_async_call.assert_called_once()


async def test_turn_on_with_rgbw(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on with rgbw."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    with patch(
        "homeassistant.components.aidot.coordinator.DeviceClient.async_set_rgbw",
        new_callable=AsyncMock,
    ) as mock_async_call:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
            blocking=True,
        )
        mock_async_call.assert_called_once()
