"""Tests for light platform."""

from homeassistant.components import wiz
from homeassistant.const import CONF_HOST, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import FAKE_IP, FAKE_MAC, _patch_discovery, _patch_wizlight

from tests.common import MockConfigEntry


async def test_light_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    entry = MockConfigEntry(
        domain=wiz.DOMAIN,
        unique_id=FAKE_MAC,
        data={CONF_HOST: FAKE_IP},
    )
    entry.add_to_hass(hass)
    with _patch_discovery(), _patch_wizlight():
        await async_setup_component(hass, wiz.DOMAIN, {wiz.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.mock_title"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == FAKE_MAC
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
