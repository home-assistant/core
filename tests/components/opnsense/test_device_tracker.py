"""The tests for the opnsense device tracker platform."""
from homeassistant.components import opnsense
from homeassistant.components.opnsense.const import DOMAIN

from . import CONFIG_DATA_IMPORT, setup_mock_diagnostics

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_get_scanner(hass, mock_device_tracker_conf):
    """Test creating an opnsense scanner."""
    opnsense.OPNsenseData.hass_config = {"foo": "bar"}

    with patch(
        "homeassistant.components.opnsense.diagnostics"
    ) as mock_diagnostics, patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diagnostics_config_flow:
        setup_mock_diagnostics(mock_diagnostics)
        setup_mock_diagnostics(mock_diagnostics_config_flow)

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONFIG_DATA_IMPORT,
        )
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert result
        device_1 = hass.states.get("device_tracker.desktop")
        assert device_1 is not None
        assert device_1.state == "home"
        device_2 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
        assert device_2.state == "home"
