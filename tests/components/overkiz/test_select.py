"""Tests for the Overkiz select platform."""

from collections.abc import Generator
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
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/2733989",
    "select.siren_memorized_simple_volume",
)
ACTIVE_ZONES = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/2155276",
    "select.willow_house_protexiom_active_zones",
)


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to select only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(
        fixture=OPEN_CLOSED_PEDESTRIAN.fixture
    )

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_select_open_closed_pedestrian(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test selecting pedestrian position sends setPedestrianPosition command."""
    await setup_overkiz_integration(fixture=OPEN_CLOSED_PEDESTRIAN.fixture)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: OPEN_CLOSED_PEDESTRIAN.entity_id, ATTR_OPTION: "pedestrian"},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=OPEN_CLOSED_PEDESTRIAN.device_url,
        command_name="setPedestrianPosition",
    )


async def test_select_open_closed_partial(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test selecting partial position sends partialPosition command."""
    await setup_overkiz_integration(fixture=OPEN_CLOSED_PARTIAL.fixture)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: OPEN_CLOSED_PARTIAL.entity_id, ATTR_OPTION: "partial"},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=OPEN_CLOSED_PARTIAL.device_url,
        command_name="partialPosition",
    )


async def test_select_memorized_simple_volume(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test selecting volume sends setMemorizedSimpleVolume command."""
    await setup_overkiz_integration(fixture=MEMORIZED_SIMPLE_VOLUME.fixture)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: MEMORIZED_SIMPLE_VOLUME.entity_id,
            ATTR_OPTION: "highest",
        },
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=MEMORIZED_SIMPLE_VOLUME.device_url,
        command_name="setMemorizedSimpleVolume",
        parameters=["highest"],
    )


async def test_select_active_zones(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test selecting active zone sends alarmZoneOn command."""
    await setup_overkiz_integration(fixture=ACTIVE_ZONES.fixture)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ACTIVE_ZONES.entity_id, ATTR_OPTION: "A,B"},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=ACTIVE_ZONES.device_url,
        command_name="alarmZoneOn",
        parameters=["A,B"],
    )


async def test_select_active_zones_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test selecting empty zone sends alarmOff command."""
    await setup_overkiz_integration(fixture=ACTIVE_ZONES.fixture)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ACTIVE_ZONES.entity_id, ATTR_OPTION: ""},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=ACTIVE_ZONES.device_url,
        command_name="alarmOff",
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
