"""Test fixtures for the Open Thread Border Router integration."""
from unittest.mock import patch

import pytest

from homeassistant.components import otbr

from tests.common import MockConfigEntry

CONFIG_ENTRY_DATA = {"url": "http://core-silabs-multiprotocol:8081"}
DATASET = bytes.fromhex(
    "0E080000000000010000000300001035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
    "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
    "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
)


@pytest.fixture(name="otbr_config_entry")
async def otbr_config_entry_fixture(hass):
    """Mock Open Thread Border Router config entry."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
    )
    config_entry.add_to_hass(hass)
    with patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
