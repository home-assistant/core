"""Test the Landis + Gyr Heat Meter init."""

from homeassistant.const import CONF_DEVICE

from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test removing config entry."""
    entry = MockConfigEntry(
        domain="landisgyr_heat_meter",
        title="LUGCUH50",
        data={CONF_DEVICE: "/dev/1234"},
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "landisgyr_heat_meter" in hass.config.components

    assert await hass.config_entries.async_remove(entry.entry_id)
