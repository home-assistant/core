"""Tests for Xthings Cloud light platform."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_DEVICE_LIGHT_BRIGHTNESS_ONLY,
    MOCK_DEVICE_LIGHT_FULL,
    MOCK_DEVICE_LIGHT_ONOFF,
)

from tests.common import MockConfigEntry


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    devices: list[dict],
) -> AsyncMock:
    """Set up the integration with mock devices."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.xthings_cloud.XthingsCloudApiClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.async_get_devices = AsyncMock(return_value=devices)
        client.is_token_expired = lambda: False
        client.async_brite_on = AsyncMock()
        client.async_brite_off = AsyncMock()
        client.async_brite_brightness = AsyncMock()
        client.async_brite_color = AsyncMock()

        with patch(
            "homeassistant.components.xthings_cloud.coordinator.XthingsCloudWebSocket",
            autospec=True,
        ) as mock_ws_cls:
            mock_ws_cls.return_value.async_start = AsyncMock()
            mock_ws_cls.return_value.async_stop = AsyncMock()

            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    return client


async def test_light_full_color_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test full color light entity is created correctly."""
    await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_FULL])

    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == round(75 * 255 / 100)
    assert state.attributes[ATTR_HS_COLOR] == (150, 80)
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert ColorMode.HS in state.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert ColorMode.COLOR_TEMP in state.attributes[ATTR_SUPPORTED_COLOR_MODES]


async def test_light_brightness_only_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test brightness-only light entity."""
    await _setup_integration(
        hass,
        mock_config_entry,
        [MOCK_DEVICE_LIGHT_BRIGHTNESS_ONLY],
    )

    state = hass.states.get("light.hallway_light")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == {ColorMode.BRIGHTNESS}


async def test_light_onoff_only_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on/off only light entity."""
    await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_ONOFF])

    state = hass.states.get("light.porch_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == {ColorMode.ONOFF}


async def test_light_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a light."""
    client = await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_FULL])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.bedroom_light"},
        blocking=True,
    )
    client.async_brite_on.assert_called_once_with("dev_light_001")


async def test_light_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a light."""
    client = await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_FULL])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.bedroom_light"},
        blocking=True,
    )
    client.async_brite_off.assert_called_once_with("dev_light_001")


async def test_light_turn_on_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on with brightness."""
    client = await _setup_integration(
        hass,
        mock_config_entry,
        [MOCK_DEVICE_LIGHT_BRIGHTNESS_ONLY],
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.hallway_light",
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    client.async_brite_brightness.assert_called_once_with(
        "dev_light_002", round(128 * 100 / 255)
    )
    client.async_brite_on.assert_not_called()


async def test_light_turn_on_hs_color(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on with HS color."""
    client = await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_FULL])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.bedroom_light",
            ATTR_HS_COLOR: (200, 90),
        },
        blocking=True,
    )
    client.async_brite_color.assert_called_once_with(
        "dev_light_001",
        {
            "colortype": 0,
            "hue": 200,
            "saturation": 90,
            "lightness": 54,
            "brightness": 75,
        },
    )
    client.async_brite_on.assert_not_called()


async def test_light_turn_on_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on with color temperature."""
    client = await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_FULL])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.bedroom_light",
            ATTR_COLOR_TEMP_KELVIN: 3000,
        },
        blocking=True,
    )
    client.async_brite_color.assert_called_once_with(
        "dev_light_001",
        {
            "colortype": 1,
            "temperature": 3000,
            "brightness": 75,
        },
    )


async def test_light_turn_on_hs_color_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on with HS color and brightness."""
    client = await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_FULL])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.bedroom_light",
            ATTR_HS_COLOR: (100, 50),
            ATTR_BRIGHTNESS: 200,
        },
        blocking=True,
    )
    expected_level = round(200 * 100 / 255)
    client.async_brite_color.assert_called_once_with(
        "dev_light_001",
        {
            "colortype": 0,
            "hue": 100,
            "saturation": 50,
            "lightness": expected_level,
            "brightness": expected_level,
        },
    )


async def test_light_color_temp_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color temp with brightness override."""
    client = await _setup_integration(hass, mock_config_entry, [MOCK_DEVICE_LIGHT_FULL])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.bedroom_light",
            ATTR_COLOR_TEMP_KELVIN: 5000,
            ATTR_BRIGHTNESS: 180,
        },
        blocking=True,
    )
    client.async_brite_color.assert_called_once_with(
        "dev_light_001",
        {
            "colortype": 1,
            "temperature": 5000,
            "brightness": round(180 * 100 / 255),
        },
    )


async def test_light_unavailable_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light shows unavailable when device is offline."""
    device = deepcopy(MOCK_DEVICE_LIGHT_FULL)
    device["online"] = False
    await _setup_integration(hass, mock_config_entry, [device])

    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.state == "unavailable"


async def test_light_color_mode_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color mode is COLOR_TEMP when color_type is 1."""
    device = deepcopy(MOCK_DEVICE_LIGHT_FULL)
    device["status"]["color_type"] = 1
    await _setup_integration(hass, mock_config_entry, [device])

    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 4000
