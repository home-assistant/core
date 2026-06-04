"""Tests for the Noonlight API-reachable binary sensor."""

from httpx import Response
import respx

from homeassistant.core import HomeAssistant

from .conftest import STATUS_RE

from tests.common import MockConfigEntry

ENTITY_ID = "binary_sensor.noonlight_api_reachable"


async def test_api_reachable_on(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """A 404 probe (reachable + authorized) reports the sensor on."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "on"


@respx.mock
async def test_api_reachable_off_when_unauthorized(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A 401 probe (bad token) reports the sensor off."""
    respx.get(url__regex=STATUS_RE).mock(return_value=Response(401))

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "off"
