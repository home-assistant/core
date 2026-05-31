"""Tests for the Overkiz light platform."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizState
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
    "light.maple_residence_terrace_ceiling_light",
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


@pytest.mark.parametrize(
    ("device", "service", "service_data", "command_name", "parameters"),
    [
        (ONOFF_LIGHT, SERVICE_TURN_ON, {}, "on", None),
        (ONOFF_LIGHT, SERVICE_TURN_OFF, {}, "off", None),
        (DIMMABLE_LIGHT, SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 128}, "setIntensity", [50]),
        (DIMMABLE_LIGHT, SERVICE_TURN_ON, {}, "on", None),
        (
            RGB_LIGHT,
            SERVICE_TURN_ON,
            {ATTR_RGB_COLOR: (255, 0, 128)},
            "setRGB",
            [255, 0, 128],
        ),
        (RGB_LIGHT, SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 200}, "setIntensity", [78]),
    ],
    ids=[
        "onoff-turn-on",
        "onoff-turn-off",
        "dimmable-with-brightness",
        "dimmable-on",
        "rgb-with-color",
        "rgb-with-brightness",
    ],
)
async def test_light_service_actions(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    device: FixtureDevice,
    service: str,
    service_data: dict[str, Any],
    command_name: str,
    parameters: list[Any] | None,
) -> None:
    """Test light service calls send the expected commands."""
    await setup_overkiz_integration(fixture=device.fixture)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: device.entity_id, **service_data},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=command_name,
        parameters=parameters,
    )


async def test_light_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for a light entity."""
    await setup_overkiz_integration(fixture=DIMMABLE_LIGHT.fixture)

    assert hass.states.get(DIMMABLE_LIGHT.entity_id).state == STATE_ON

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

    assert hass.states.get(DIMMABLE_LIGHT.entity_id).state == STATE_OFF


async def test_light_rgb_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven RGB color state update."""
    await setup_overkiz_integration(fixture=RGB_LIGHT.fixture)

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

    assert hass.states.get(DIMMABLE_LIGHT.entity_id).state != STATE_UNAVAILABLE

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
