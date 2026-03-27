"""Test the SFR Box events."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from sfrbox_api.models import VoipCallHistoryCall, VoipCallHistoryList
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform

pytestmark = pytest.mark.usefixtures(
    "system_get_info",
    "dsl_get_info",
    "voip_get_info",
    "voip_get_call_history_list",
    "wan_get_info",
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS_WITH_AUTH."""
    with (
        patch("homeassistant.components.sfr_box.PLATFORMS_WITH_AUTH", [Platform.EVENT]),
        patch("homeassistant.components.sfr_box.coordinator.SFRBox.authenticate"),
    ):
        yield


async def test_events(
    hass: HomeAssistant,
    config_entry_with_auth: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for SFR Box events."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_auth.entry_id
    )


async def test_events_trigger_on_coordinator_update(
    hass: HomeAssistant,
    config_entry_with_auth: ConfigEntry,
) -> None:
    """Test that event entity updates on coordinator update."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    # Get the coordinator to access the event entity
    entry_data = config_entry_with_auth.runtime_data
    coordinator = entry_data.voip_callhistorylist

    # Find the event entity - should be named event.voip_callhistorylist
    state = hass.states.get("event.sfr_box_voip_call_history")
    assert state is not None, "Event entity should be created"

    # Update the coordinator with new data
    coordinator.async_set_updated_data(
        VoipCallHistoryList(
            calls=[
                VoipCallHistoryCall(
                    type="voip",
                    direction="outgoing",
                    number="0123456789",
                    length=120,
                    date=1774309700,
                ),
            ],
        )
    )
    await hass.async_block_till_done()

    # Check the entity state and attributes have been updated
    state = hass.states.get("event.sfr_box_voip_call_history")
    assert state is not None

    # Verify event was triggered
    assert state.attributes[ATTR_EVENT_TYPE] == "outgoing"
    assert state.attributes["type"] == "voip"
    assert state.attributes["direction"] == "outgoing"
    assert state.attributes["number"] == "0123456789"
    assert state.attributes["length"] == 120
    assert state.attributes["date"] == 1774309700

    # Update the coordinator with new data
    coordinator.async_set_updated_data(
        VoipCallHistoryList(
            calls=[
                VoipCallHistoryCall(
                    type="voip",
                    direction="outgoing",
                    number="0123456789",
                    length=120,
                    date=1774309700,
                ),
                VoipCallHistoryCall(
                    type="voip",
                    direction="incoming",
                    number="0234567890",
                    length=-1,
                    date=1774309800,
                ),
            ],
        )
    )
    await hass.async_block_till_done()

    # Check the entity state and attributes have been updated
    state = hass.states.get("event.sfr_box_voip_call_history")
    assert state is not None

    # Verify event was triggered
    assert state.attributes[ATTR_EVENT_TYPE] == "missed"
    assert state.attributes["type"] == "voip"
    assert state.attributes["direction"] == "incoming"
    assert state.attributes["number"] == "0234567890"
    assert state.attributes["length"] == -1
    assert state.attributes["date"] == 1774309800
