"""The tests for the london_underground platform."""

from homeassistant.components.london_underground.const import CONF_LINE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    "sensor": {"platform": "london_underground", CONF_LINE: ["Metropolitan"]}
}


async def test_valid_state(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
) -> None:
    """Test for operational london_underground sensor with proper attributes."""
    # Set up via YAML which will trigger import and set up the config entry
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    # Verify the config entry was created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Verify a warning was issued about YAML deprecation
    assert issue_registry.async_get_issue(DOMAIN, "yaml_deprecated")

    # Check the state after setup completes
    state = hass.states.get("sensor.london_underground_metropolitan")
    assert state
    assert state.state == "Good Service"
    assert state.attributes == {
        "Description": "Nothing to report",
        "attribution": "Powered by TfL Open Data",
        "friendly_name": "London Underground Metropolitan",
        "icon": "mdi:subway",
    }
