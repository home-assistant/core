"""Tests for the Overkiz light platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

ONOFF_LIGHT = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/11944017",
    "light.terrace_ceiling_light",
)
DIMMABLE_LIGHT = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_3.json",
    "io://1234-5678--9373/1170079",
    "light.guest_room_ceiling_light",
)
RGB_LIGHT = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json",
    "io://1234-5678-3293/14608095",
    "light.light_terras_rgb",
)

SNAPSHOT_FIXTURES = [
    ONOFF_LIGHT,
    DIMMABLE_LIGHT,
    RGB_LIGHT,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to light only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.LIGHT]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_light_onoff_turn_on(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on an on/off light sends the on command."""
    await setup_overkiz_integration(fixture=ONOFF_LIGHT.fixture)

    state = hass.states.get(ONOFF_LIGHT.entity_id)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ONOFF_LIGHT.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=ONOFF_LIGHT.device_url,
        command_name="on",
    )


async def test_light_onoff_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning off an on/off light sends the off command."""
    await setup_overkiz_integration(fixture=ONOFF_LIGHT.fixture)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ONOFF_LIGHT.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=ONOFF_LIGHT.device_url,
        command_name="off",
    )


async def test_light_dimmable_turn_on_with_brightness(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on a dimmable light with brightness sends setIntensity."""
    await setup_overkiz_integration(fixture=DIMMABLE_LIGHT.fixture)

    state = hass.states.get(DIMMABLE_LIGHT.entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DIMMABLE_LIGHT.entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DIMMABLE_LIGHT.device_url,
        command_name="setIntensity",
        parameters=[50],
    )


async def test_light_dimmable_turn_on_without_brightness(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on a dimmable light without brightness sends on command."""
    await setup_overkiz_integration(fixture=DIMMABLE_LIGHT.fixture)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DIMMABLE_LIGHT.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DIMMABLE_LIGHT.device_url,
        command_name="on",
    )


async def test_light_dimmable_brightness_value(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test brightness is converted from 0-100% to 0-255 range."""
    await setup_overkiz_integration(fixture=DIMMABLE_LIGHT.fixture)

    state = hass.states.get(DIMMABLE_LIGHT.entity_id)
    assert state
    # Fixture has core:LightIntensityState = 56, so brightness = round(56 * 255 / 100) = 143
    assert state.attributes[ATTR_BRIGHTNESS] == 143


async def test_light_rgb_turn_on_with_color(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on an RGB light with color sends setRGB."""
    await setup_overkiz_integration(fixture=RGB_LIGHT.fixture)

    state = hass.states.get(RGB_LIGHT.entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert state.attributes[ATTR_RGB_COLOR] == (128, 64, 200)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: RGB_LIGHT.entity_id, ATTR_RGB_COLOR: (255, 0, 128)},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=RGB_LIGHT.device_url,
        command_name="setRGB",
        parameters=[255, 0, 128],
    )


async def test_light_rgb_turn_on_with_brightness(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on an RGB light with brightness sends setIntensity."""
    await setup_overkiz_integration(fixture=RGB_LIGHT.fixture)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: RGB_LIGHT.entity_id, ATTR_BRIGHTNESS: 200},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=RGB_LIGHT.device_url,
        command_name="setIntensity",
        parameters=[78],
    )


async def test_light_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for a light entity."""
    await setup_overkiz_integration(fixture=DIMMABLE_LIGHT.fixture)

    state = hass.states.get(DIMMABLE_LIGHT.entity_id)
    assert state
    assert state.state == STATE_ON

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=DIMMABLE_LIGHT.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_ON_OFF.value,
                        "type": 3,
                        "value": "off",
                    },
                    {
                        "name": OverkizState.CORE_LIGHT_INTENSITY.value,
                        "type": 1,
                        "value": 0,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(DIMMABLE_LIGHT.entity_id)
    assert state.state == STATE_OFF


async def test_light_rgb_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven RGB color state update."""
    await setup_overkiz_integration(fixture=RGB_LIGHT.fixture)

    state = hass.states.get(RGB_LIGHT.entity_id)
    assert state
    assert state.attributes[ATTR_RGB_COLOR] == (128, 64, 200)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=RGB_LIGHT.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_RED_COLOR_INTENSITY.value,
                        "type": 1,
                        "value": 10,
                    },
                    {
                        "name": OverkizState.CORE_GREEN_COLOR_INTENSITY.value,
                        "type": 1,
                        "value": 20,
                    },
                    {
                        "name": OverkizState.CORE_BLUE_COLOR_INTENSITY.value,
                        "type": 1,
                        "value": 30,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(RGB_LIGHT.entity_id)
    assert state.attributes[ATTR_RGB_COLOR] == (10, 20, 30)


async def test_light_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test light becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=DIMMABLE_LIGHT.fixture)

    state = hass.states.get(DIMMABLE_LIGHT.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=DIMMABLE_LIGHT.device_url,
            )
        ],
    )

    assert hass.states.get(DIMMABLE_LIGHT.entity_id).state == STATE_UNAVAILABLE
