"""Test Brottsplatskartan component setup process."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.scrape.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MockRestData

from tests.common import MockConfigEntry

TEST_CONFIG = {
    "resource": "https://www.home-assistant.io",
    "name": "Release",
    "select": ".current-version h1",
    "value_template": "{{ value.split(':')[1] }}",
    "index": 0,
    "verify_ssl": True,
}


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options=TEST_CONFIG,
        title="Release",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=MockRestData("test_scrape_sensor"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.release")
    assert state


async def test_remove_entry(hass: HomeAssistant) -> None:
    """Test remove entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options=TEST_CONFIG,
        title="Release",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.scrape.sensor.RestData",
        return_value=MockRestData("test_scrape_sensor"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.release")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.release")
    assert not state
