"""Tests for the oncue binary_sensor."""
from __future__ import annotations

from homeassistant.components import oncue
from homeassistant.components.oncue.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import _patch_login_and_data

from tests.common import MockConfigEntry


async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Test that the binary sensors are setup with the expected values."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "any", CONF_PASSWORD: "any"},
        unique_id="any",
    )
    config_entry.add_to_hass(hass)
    with _patch_login_and_data():
        await async_setup_component(hass, oncue.DOMAIN, {oncue.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert len(hass.states.async_all("binary_sensor")) == 1
    assert (
        hass.states.get(
            "binary_sensor.my_generator_network_connection_established"
        ).state
        == STATE_ON
    )
