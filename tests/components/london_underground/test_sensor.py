"""The tests for the london_underground platform."""

from homeassistant.components.london_underground.const import CONF_LINE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

VALID_CONFIG = {
    "sensor": {"platform": "london_underground", CONF_LINE: ["Metropolitan"]}
}


async def test_valid_state(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
) -> None:
    """Test operational London Underground sensor using a mock config entry."""
    # Create a mock config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},  # The integration stores no data, only options
        options={CONF_LINE: ["Metropolitan"]},
        title="London Underground",
    )
    # Add and set up the entry
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Ensure the entry is fully loaded
    assert entry.state is ConfigEntryState.LOADED

    # Confirm that the expected entity exists and is correct
    state = hass.states.get("sensor.london_underground_metropolitan")
    assert state is not None
    assert state.state == "Good Service"
    assert state.attributes == {
        "Description": "Nothing to report",
        "attribution": "Powered by TfL Open Data",
        "friendly_name": "London Underground Metropolitan",
        "icon": "mdi:subway",
    }

    # No YAML warning should be issued, since setup was not via YAML
    assert not issue_registry.async_get_issue(DOMAIN, "yaml_deprecated")
