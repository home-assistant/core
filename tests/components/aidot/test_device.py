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
            "homeassistant.components.aidot.light.AidotCoordinator", return_value=Mock()
        ),
        patch(
            "homeassistant.components.aidot.coordinator.Discover.broadcast_message",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aidot.coordinator.AidotClient.async_get_all_device",
            return_value=mock_device_list(),
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


def _mocked_bulb():
    bulb = Mock()
    bulb.connectAndLogin = True
    bulb.available = True
    bulb.is_on = True
    bulb.brightness = 255
    bulb.cct = 3000
    bulb.rgdb = 0xFFFFFFFF
    bulb.colorMode = "rgbw"
    bulb.sendDevAttr = AsyncMock()
    bulb.getDimingAction = Mock(return_value={"dim": 100})
    bulb.getCCTAction = Mock(return_value={"cct": 3000})
    bulb.getRGBWAction = Mock(return_value={"rgbw": 0xFFFFFFFF})
    bulb.getOnOffAction = Mock(return_value={"OnOff": 1})
    return bulb


def _patch_mock_bulb(bulb: Mock):
    return patch(
        "homeassistant.components.aidot.light.Lan",
        return_value=bulb,
    )


async def test_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    mocked_bulb = _mocked_bulb()
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
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
    mocked_bulb = _mocked_bulb()
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
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
    mocked_bulb = _mocked_bulb()
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
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
    mocked_bulb = _mocked_bulb()
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_bulb.sendDevAttr.assert_called_once_with({"OnOff": 1})


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn off."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    mocked_bulb = _mocked_bulb()
    mocked_bulb.getOnOffAction = Mock(return_value={"OnOff": 0})
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_bulb.sendDevAttr.assert_called_once_with({"OnOff": 0})


async def test_trun_on_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on brightness."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    mocked_bulb = _mocked_bulb()
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    mocked_bulb.sendDevAttr.assert_called_once_with({"dim": 100})


async def test_turn_on_with_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on with color temp."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    mocked_bulb = _mocked_bulb()
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )
    mocked_bulb.sendDevAttr.assert_called_once_with({"cct": 3000})


async def test_turn_on_with_rgbw(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn on with rgbw."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    mocked_bulb = _mocked_bulb()
    with (
        _patch_mock_bulb(mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    mocked_bulb.sendDevAttr.assert_called_once_with({"rgbw": 0xFFFFFFFF})
