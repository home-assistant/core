"""Tests for the Overkiz select platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

OPEN_CLOSED_PEDESTRIAN = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/877679",
    "select.living_room_garden_gate_position",
)
OPEN_CLOSED_PARTIAL = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/7433515",
    "select.living_room_partial_garage_door_position",
)
MEMORIZED_SIMPLE_VOLUME = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json",
    "io://1234-5678-3293/2733989",
    "select.siren_memorized_simple_volume",
)
ACTIVE_ZONES = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/2155276",
    "select.willow_house_protexiom_active_zones",
)

# One representative setup per fixture file; both expose select entities.
SNAPSHOT_FIXTURES = [
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "setup/local_somfy_tahoma_v2_europe.json",
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to select only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.parametrize(
    "fixture",
    SNAPSHOT_FIXTURES,
    ids=[Path(fixture).name for fixture in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fixture: str,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("device", "option", "command_name", "parameters"),
    [
        pytest.param(
            OPEN_CLOSED_PEDESTRIAN,
            "pedestrian",
            "setPedestrianPosition",
            None,
            id="pedestrian",
        ),
        pytest.param(
            OPEN_CLOSED_PARTIAL,
            "partial",
            "partialPosition",
            None,
            id="partial",
        ),
        pytest.param(
            MEMORIZED_SIMPLE_VOLUME,
            "highest",
            "setMemorizedSimpleVolume",
            ["highest"],
            id="memorized_simple_volume",
        ),
        pytest.param(
            ACTIVE_ZONES,
            "A,B",
            "alarmZoneOn",
            ["A,B"],
            id="active_zones",
        ),
        pytest.param(
            ACTIVE_ZONES,
            "",
            "alarmOff",
            None,
            id="active_zones_off",
        ),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    device: FixtureDevice,
    option: str,
    command_name: str,
    parameters: list[str] | None,
) -> None:
    """Test selecting an option sends the expected command."""
    await setup_overkiz_integration(fixture=device.fixture)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: device.entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=command_name,
        parameters=parameters,
    )


async def test_select_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=OPEN_CLOSED_PEDESTRIAN.fixture)

    state = hass.states.get(OPEN_CLOSED_PEDESTRIAN.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=OPEN_CLOSED_PEDESTRIAN.device_url,
            )
        ],
    )

    assert hass.states.get(OPEN_CLOSED_PEDESTRIAN.entity_id).state == STATE_UNAVAILABLE
