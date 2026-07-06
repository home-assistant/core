"""Tests for the Overkiz climate platform."""

from collections.abc import Generator
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
from pyoverkiz.models import Event
import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    async_deliver_events,
    device_available_event,
    device_removed_event,
    device_state_changed_event,
    device_unavailable_event,
)

VALVE = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#1",
    "climate.maple_residence_garden_radiator",
)

# Atlantic MODBUSLINK heater that does not expose core:RegulationModeState,
# io:TargetHeatingLevelState. See https://github.com/home-assistant/core/issues/175812.
MODBUSLINK_HEATER = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "modbuslink://1234-5678-5643/1#1",
    "climate.living_room_heater",
)


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to climate only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.CLIMATE]):
        yield


async def test_valve_hvac_action_none_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test that hvac_action handles None valve state without crashing."""
    await setup_overkiz_integration(fixture=VALVE.fixture)

    state = hass.states.get(VALVE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE

    # Deliver an event that clears the valve state
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=VALVE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_OPEN_CLOSED_VALVE,
                        "type": 3,
                        "value": None,
                    }
                ],
            )
        ],
    )

    # hvac_action should be None (unknown) rather than raising KeyError
    state = hass.states.get(VALVE.entity_id)
    assert state is not None
    assert state.attributes.get(ATTR_HVAC_ACTION) is None


async def test_modbuslink_heater_loads_without_regulation_mode(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test Atlantic MODBUSLINK heater loads when optional states are missing."""
    await setup_overkiz_integration(fixture=MODBUSLINK_HEATER.fixture)

    state = hass.states.get(MODBUSLINK_HEATER.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_HVAC_ACTION) == HVACAction.OFF
    assert state.attributes.get(ATTR_PRESET_MODE) is None


UNKNOWN_DEVICE_URL = "zigbee://1234-5678-1698/65535"


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(device_available_event(UNKNOWN_DEVICE_URL), id="available"),
        pytest.param(device_unavailable_event(UNKNOWN_DEVICE_URL), id="unavailable"),
        pytest.param(
            device_state_changed_event(
                UNKNOWN_DEVICE_URL,
                [{"name": "core:OnOffState", "type": 3, "value": "on"}],
            ),
            id="state_changed",
        ),
        pytest.param(device_removed_event(UNKNOWN_DEVICE_URL), id="removed"),
    ],
)
async def test_events_for_unknown_device_url(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    event: Event,
) -> None:
    """Test that events for unknown device URLs don't crash the coordinator."""
    await setup_overkiz_integration(fixture=VALVE.fixture)

    await async_deliver_events(hass, freezer, mock_client, [event])

    # Should not crash; valve entity should still be available
    state = hass.states.get(VALVE.entity_id)
    assert state is not None
