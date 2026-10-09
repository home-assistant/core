"""Test the roon media player."""

from unittest.mock import MagicMock, patch

from homeassistant.components.media_player import ATTR_GROUP_MEMBERS
from homeassistant.components.roon.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    EVENT_STATE_CHANGED,
    EVENT_STATE_REPORTED,
)
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_capture_events

KITCHEN_ENTITY_ID = "media_player.kitchen"
LOUNGE_ENTITY_ID = "media_player.lounge"
RENAMED_ENTITY_ID = "media_player.renamed"


async def test_group_members_follow_renamed_group_member(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test group members report the new entity_id of another renamed player."""
    source_controls = [
        {"display_name": "Speaker", "supports_standby": False, "status": "selected"}
    ]
    roonapi = MagicMock()
    roonapi.zones = {
        "zone_1": {
            "zone_id": "zone_1",
            "display_name": "Kitchen + Lounge",
            "state": "stopped",
            "settings": {"loop": "disabled", "shuffle": False},
            "outputs": [
                {
                    "output_id": "output_1",
                    "display_name": "Kitchen",
                    "source_controls": source_controls,
                },
                {
                    "output_id": "output_2",
                    "display_name": "Lounge",
                    "source_controls": source_controls,
                },
            ],
        }
    }
    roonapi.grouped_zone_names.return_value = ["Kitchen", "Lounge"]
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.1.1.1", CONF_API_KEY: "api_key"}
    )
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.roon.server.RoonApi", return_value=roonapi):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await config_entry.runtime_data.async_update_players()
        await hass.async_block_till_done()

    state = hass.states.get(LOUNGE_ENTITY_ID)
    assert state.attributes[ATTR_GROUP_MEMBERS] == [
        KITCHEN_ENTITY_ID,
        LOUNGE_ENTITY_ID,
    ]
    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    state_reports: list[Event[EventStateReportedData]] = []

    @callback
    def _is_renamed(data: EventStateReportedData) -> bool:
        return data["entity_id"] == RENAMED_ENTITY_ID

    @callback
    def _capture_report(event: Event[EventStateReportedData]) -> None:
        state_reports.append(event)

    hass.bus.async_listen(
        EVENT_STATE_REPORTED, _capture_report, event_filter=_is_renamed
    )

    entity_registry.async_update_entity(
        KITCHEN_ENTITY_ID, new_entity_id=RENAMED_ENTITY_ID
    )
    await hass.async_block_till_done()

    for entity_id in (RENAMED_ENTITY_ID, LOUNGE_ENTITY_ID):
        state = hass.states.get(entity_id)
        assert state.attributes[ATTR_GROUP_MEMBERS] == [
            RENAMED_ENTITY_ID,
            LOUNGE_ENTITY_ID,
        ]
    # The renamed player's state is written once under the new entity_id; a
    # repeated identical write would be a state report
    assert [
        event.data["old_state"]
        for event in state_changes
        if event.data["entity_id"] == RENAMED_ENTITY_ID
    ] == [None]
    assert not state_reports

    assert await hass.config_entries.async_unload(config_entry.entry_id)
