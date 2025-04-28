"""The tests for the nexbus component."""

from homeassistant.components.nextbus.const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_STOP
from homeassistant.core import HomeAssistant

from .const import VALID_AGENCY_TITLE, VALID_ROUTE_TITLE, VALID_STOP_TITLE

from tests.common import MockConfigEntry


async def assert_setup_sensor(
    hass: HomeAssistant,
    config: dict[str, dict[str, str]],
    expected_state=ConfigEntryState.LOADED,
    route_title: str = VALID_ROUTE_TITLE,
) -> MockConfigEntry:
    """Set up the sensor and assert it's been created."""
    unique_id = f"{config[DOMAIN][CONF_AGENCY]}_{config[DOMAIN][CONF_ROUTE]}_{config[DOMAIN][CONF_STOP]}"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config[DOMAIN],
        title=f"{VALID_AGENCY_TITLE} {route_title} {VALID_STOP_TITLE}",
        unique_id=unique_id,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state

    return config_entry
