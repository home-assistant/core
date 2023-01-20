"""Test the Anova sensors."""

from unittest.mock import patch

from . import ONLINE_UPDATE, create_entry


async def test_sensors(hass):
    """Test setting up creates the sensors."""
    entry = create_entry(hass)
    assert len(hass.states.async_all("sensor")) == 0
    with patch("anova_wifi.AnovaPrecisionCooker.update") as update_patch:
        update_patch.return_value = ONLINE_UPDATE
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 9
