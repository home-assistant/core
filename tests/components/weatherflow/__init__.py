"""Tests for the WeatherFlow integration."""

from pyweatherflowudp.aioudp import LocalEndpoint

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture_bytes

HUB_ADDRESS = ("192.0.2.1", 50222)


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    endpoint: LocalEndpoint,
    packets: tuple[str, ...] = ("device.json", "obs_st.json"),
) -> None:
    """Set up the integration and receive UDP packets, by default of a Tempest."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    for fixture in packets:
        endpoint.feed_datagram(load_fixture_bytes(fixture, "weatherflow"), HUB_ADDRESS)
    await hass.async_block_till_done()
