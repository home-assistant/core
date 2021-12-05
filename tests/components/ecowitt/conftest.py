"""Test the Ecowitt config flow."""
from unittest.mock import MagicMock, patch

from pyecowitt import EcoWittListener

from homeassistant.components.ecowitt.const import (
    DATA_MODEL,
    DATA_PASSKEY,
    DOMAIN as ECOWITT_DOMAIN,
)
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_DATA = {CONF_PORT: 4199}

MOCK_SENSORS = {DATA_MODEL: "GW1000", DATA_PASSKEY: "FakeEcowitt"}


def _init_ecowitt(data_mock):
    """Mock the ecowitt library."""

    def get_sensor_value_by_key(key):
        return MOCK_SENSORS[key]

    ecowitt = MagicMock(EcoWittListener(data_mock[CONF_PORT]))
    ecowitt.get_sensor_value_by_key = get_sensor_value_by_key

    return ecowitt


async def _mock_ecowitt(hass: HomeAssistant, data_mock, options):
    """Mock an ecowitt."""
    config_entry = MockConfigEntry(domain=ECOWITT_DOMAIN, data=data_mock)
    config_entry.options = options
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ecowitt.EcoWittListener",
        return_value=_init_ecowitt(data_mock),
        autospec=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
