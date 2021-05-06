"""Test the Aurora ABB PowerOne Solar PV sensors."""
from unittest.mock import patch

from homeassistant.components.aurora_abb_powerone.const import (
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry


async def test_sensors(hass):
    """Test data coming back from inverter."""
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title=DEFAULT_INTEGRATION_TITLE,
        data={
            CONF_PORT: "/dev/usb999",
            CONF_ADDRESS: 3,
        },
        source="dummysource",
        system_options={},
        entry_id="13579",
    )

    def _simulated_returns(index, global_measure=None):
        returns = {
            3: 45.678,  # power
            21: 9.876,  # temperature
        }
        return returns[index]

    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=_simulated_returns,
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        power = hass.states.get("sensor.power_output")
        assert power
        assert power.state == "45.7"

        temperature = hass.states.get("sensor.temperature")
        assert temperature
        assert temperature.state == "9.9"
