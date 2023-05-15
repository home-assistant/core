"""Test fixtures for the Open Thread Border Router integration."""
from unittest.mock import patch

import pytest

from homeassistant.components import otbr

from . import CONFIG_ENTRY_DATA, DATASET_CH16

from tests.common import MockConfigEntry


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
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "homeassistant.components.otbr.util.compute_pskc"
    ):  # Patch to speed up tests
        assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf):
    """Mock zeroconf in all tests."""
