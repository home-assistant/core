"""Tests for the Overkiz climate platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, OverkizState
import pytest

from homeassistant.components.climate import ATTR_HVAC_ACTION, HVACAction
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import async_deliver_events, build_event

VALVE = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#1",
    "climate.maple_residence_garden_radiator",
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
            build_event(
                EventName.DEVICE_STATE_CHANGED,
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


@pytest.mark.parametrize(
    ("event_name", "device_states"),
    [
        pytest.param(EventName.DEVICE_AVAILABLE, None, id="available"),
        pytest.param(EventName.DEVICE_UNAVAILABLE, None, id="unavailable"),
        pytest.param(
            EventName.DEVICE_STATE_CHANGED,
            [{"name": "core:OnOffState", "type": 3, "value": "on"}],
            id="state_changed",
        ),
        pytest.param(EventName.DEVICE_REMOVED, None, id="removed"),
    ],
)
async def test_events_for_unknown_device_url(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    event_name: EventName,
    device_states: list[dict[str, Any]] | None,
) -> None:
    """Test that events for unknown device URLs don't crash the coordinator."""
    await setup_overkiz_integration(fixture=VALVE.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                event_name,
                device_url="zigbee://1234-5678-1698/65535",
                device_states=device_states,
            )
        ],
    )

    # Should not crash; valve entity should still be available
    state = hass.states.get(VALVE.entity_id)
    assert state is not None
