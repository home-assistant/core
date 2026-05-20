"""Tests for Xthings Cloud light platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_lights(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test light entities are created correctly."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_TURN_ON, "async_brite_on"),
        (SERVICE_TURN_OFF, "async_brite_off"),
    ],
)
async def test_light_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    service: str,
    method: str,
) -> None:
    """Test turning on and off a light."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "light.bedroom_light"},
        blocking=True,
    )
    getattr(mock_api_client, method).assert_called_once_with("dev_light_001")


async def test_light_turn_on_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test turning on with brightness."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.hallway_light",
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    mock_api_client.async_brite_brightness.assert_called_once_with(
        "dev_light_002", round(128 * 100 / 255)
    )
    mock_api_client.async_brite_on.assert_not_called()


async def test_light_turn_on_hs_color(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test turning on with HS color."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.bedroom_light",
            ATTR_HS_COLOR: (200, 90),
        },
        blocking=True,
    )
    mock_api_client.async_brite_color.assert_called_once_with(
        "dev_light_001",
        {
            "colortype": 0,
            "hue": 200,
            "saturation": 90,
            "lightness": 54,
            "brightness": 75,
        },
    )
    mock_api_client.async_brite_on.assert_not_called()


async def test_light_turn_on_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test turning on with color temperature."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.bedroom_light",
            ATTR_COLOR_TEMP_KELVIN: 3000,
        },
        blocking=True,
    )
    mock_api_client.async_brite_color.assert_called_once_with(
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
    mock_api_client: AsyncMock,
) -> None:
    """Test turning on with HS color and brightness."""
    await setup_integration(hass, mock_config_entry)

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
    mock_api_client.async_brite_color.assert_called_once_with(
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
    mock_api_client: AsyncMock,
) -> None:
    """Test color temp with brightness override."""
    await setup_integration(hass, mock_config_entry)

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
    mock_api_client.async_brite_color.assert_called_once_with(
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
    mock_api_client: AsyncMock,
) -> None:
    """Test light shows unavailable when device is offline."""
    get_device_by_id(mock_api_client, "dev_light_001")["online"] = False
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_light_color_mode_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test color mode is COLOR_TEMP when color_type is 1."""
    get_device_by_id(mock_api_client, "dev_light_001")["status"]["color_type"] = 1
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 4000


async def test_updating_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
) -> None:
    """Test updating state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.attributes[ATTR_BRIGHTNESS] == 191

    mock_websocket.call_args[1]["on_device_status"](
        "dev_light_001",
        {
            "on": True,
            "brightness": 100,
            "color_type": 0,
            "hue": 150,
            "saturation": 80,
            "lightness": 54,
            "temperature": 4000,
        },
    )

    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.attributes[ATTR_BRIGHTNESS] == 255
