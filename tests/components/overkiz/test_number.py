"""Tests for the Overkiz number platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

MEMORIZED_POSITION = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/12184029",
    "number.office_garden_house_shutter_my_position",
)
OFFICE_BLINDS_MEMORIZED_POSITION = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe.json",
    "io://1234-5678-6508/4877511",
    "number.office_blinds_my_position",
)
EXPECTED_NUMBER_OF_SHOWER = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/109286#1",
    "number.my_home_patio_water_heating_expected_number_of_shower",
)
COMFORT_ROOM_TEMPERATURE = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "ovp://1234-5678-1698/374762#1",
    "number.maple_residence_terrace_radiator_comfort_room_temperature",
)

SNAPSHOT_FIXTURES = [
    MEMORIZED_POSITION,
    OFFICE_BLINDS_MEMORIZED_POSITION,
    EXPECTED_NUMBER_OF_SHOWER,
    COMFORT_ROOM_TEMPERATURE,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to number only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_number_set_value(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test setting a number value sends the correct command."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.state == "4"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: EXPECTED_NUMBER_OF_SHOWER.entity_id, ATTR_VALUE: 3},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=EXPECTED_NUMBER_OF_SHOWER.device_url,
        command_name="setExpectedNumberOfShower",
        parameters=[3],
    )


async def test_number_dynamic_min_max(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test that min/max values are read from device states when available."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.attributes["min"] == 2
    assert state.attributes["max"] == 4


async def test_number_state_update(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event-driven state update for a number entity."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.state == "4"

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=EXPECTED_NUMBER_OF_SHOWER.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_EXPECTED_NUMBER_OF_SHOWER.value,
                        "type": 1,
                        "value": 3,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state.state == "3"


async def test_number_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test number becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=EXPECTED_NUMBER_OF_SHOWER.fixture)

    state = hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=EXPECTED_NUMBER_OF_SHOWER.device_url,
            )
        ],
    )

    assert (
        hass.states.get(EXPECTED_NUMBER_OF_SHOWER.entity_id).state == STATE_UNAVAILABLE
    )
