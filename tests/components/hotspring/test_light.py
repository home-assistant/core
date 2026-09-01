"""Tests for the Hot Spring light platform."""

from unittest.mock import MagicMock

from hotspring import (
    HotSpringConnectionError,
    HotSpringError,
    LightColor,
    LightWheelMode,
    LightZone,
    Spa,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "light.connectedspa_ddeeff_light_zone_1"


async def test_light_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the light entity state."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on_default(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test turning on light with default settings."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "off"
    assert state.attributes.get(ATTR_BRIGHTNESS) is None

    def _set_light_brightness(zone: int, brightness: int) -> None:
        device_fixture.light_zones[0].intensity = brightness
        device_fixture.light_zones[0].is_on = brightness > 0

    mock_hotspring.set_light_brightness.side_effect = _set_light_brightness

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_hotspring.set_light_brightness.assert_called_once_with(1, 5)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255


async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test turning on light with brightness."""

    def _set_light_brightness(zone: int, brightness: int) -> None:
        device_fixture.light_zones[0].intensity = brightness
        device_fixture.light_zones[0].is_on = brightness > 0

    mock_hotspring.set_light_brightness.side_effect = _set_light_brightness

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_BRIGHTNESS: 153,
        },
        blocking=True,
    )

    mock_hotspring.set_light_brightness.assert_called_once_with(1, 3)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get(ATTR_BRIGHTNESS) == 153


async def test_turn_on_with_rgb_color_when_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test turning on light with rgb color when light is off."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_RGB_COLOR: (120, 200, 50),
        },
        blocking=True,
    )

    mock_hotspring.set_light_rgb.assert_called_once_with(1, 120, 200, 50)
    mock_hotspring.set_light_brightness.assert_called_once_with(1, 5)


async def test_turn_on_with_rgb_color_when_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test setting rgb color when light is already on."""
    device_fixture.light_zones = [
        LightZone(
            zone_id=1,
            is_enabled=True,
            is_on=True,
            color=LightColor.BLUE,
            light_wheel=LightWheelMode.OFF,
            intensity=3,
            loop_speed=0,
        ),
    ]
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_RGB_COLOR: (120, 200, 50),
        },
        blocking=True,
    )

    mock_hotspring.set_light_rgb.assert_called_once_with(1, 120, 200, 50)
    mock_hotspring.set_light_brightness.assert_not_called()


async def test_turn_on_with_rgb_color_and_brightness(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test turning on light with rgb color and brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_RGB_COLOR: (120, 200, 50),
            ATTR_BRIGHTNESS: 102,
        },
        blocking=True,
    )

    mock_hotspring.set_light_rgb.assert_called_once_with(1, 120, 200, 50)
    mock_hotspring.set_light_brightness.assert_called_once_with(1, 2)


async def test_rgb_color_active_custom(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test rgb_color property returns custom RGB values when active."""
    device_fixture.light_zones = [
        LightZone(
            zone_id=1,
            is_enabled=True,
            is_on=True,
            color=LightColor.CUSTOM,
            light_wheel=LightWheelMode.OFF,
            intensity=3,
            loop_speed=0,
            c_red=120,
            c_green=200,
            c_blue=50,
            rgb_state="active",
        ),
    ]
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("rgb_color") == (120, 200, 50)


async def test_rgb_color_all_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test rgb_color property returns (0, 0, 0) when rgb_state is active."""
    device_fixture.light_zones = [
        LightZone(
            zone_id=1,
            is_enabled=True,
            is_on=True,
            color=LightColor.CUSTOM,
            light_wheel=LightWheelMode.OFF,
            intensity=3,
            loop_speed=0,
            c_red=0,
            c_green=0,
            c_blue=0,
            rgb_state="active",
        ),
    ]
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("rgb_color") == (0, 0, 0)


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test turning off light."""
    device_fixture.light_zones = [
        LightZone(
            zone_id=1,
            is_enabled=True,
            is_on=True,
            color=LightColor.BLUE,
            light_wheel=LightWheelMode.OFF,
            intensity=5,
            loop_speed=0,
        ),
    ]
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])

    def _turn_off_light(zone: int) -> None:
        device_fixture.light_zones[0].intensity = 0
        device_fixture.light_zones[0].is_on = False

    mock_hotspring.turn_off_light.side_effect = _turn_off_light

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "on"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_hotspring.turn_off_light.assert_called_once_with(1)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "off"


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_turn_on_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when turning on light."""
    mock_hotspring.set_light_brightness.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_turn_off_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when turning off light."""
    mock_hotspring.turn_off_light.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_disabled_zone_not_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabled light zones are not added to entity registry."""
    device_fixture.light_zones = [
        LightZone(
            zone_id=1,
            is_enabled=False,
            is_on=False,
            color=LightColor.UNKNOWN,
            light_wheel=LightWheelMode.OFF,
            intensity=0,
            loop_speed=0,
        ),
    ]
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])

    assert not entity_registry.async_is_registered(ENTITY_ID)
