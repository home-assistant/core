"""Test fixtures for the Open Thread Border Router integration."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import otbr
from homeassistant.core import HomeAssistant

from . import (
    CONFIG_ENTRY_DATA_MULTIPAN,
    CONFIG_ENTRY_DATA_THREAD,
    DATASET_CH16,
    TEST_BORDER_AGENT_ID,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="otbr_config_entry_multipan")
async def otbr_config_entry_multipan_fixture(hass):
    """Mock Open Thread Border Router config entry."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "python_otbr_api.OTBR.get_border_agent_id", return_value=TEST_BORDER_AGENT_ID
    ), patch(
        "homeassistant.components.otbr.util.compute_pskc"
    ):  # Patch to speed up tests
        assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.fixture(name="otbr_config_entry_thread")
async def otbr_config_entry_thread_fixture(hass):
    """Mock Open Thread Border Router config entry."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_THREAD,
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "python_otbr_api.OTBR.get_border_agent_id", return_value=TEST_BORDER_AGENT_ID
    ), patch(
        "homeassistant.components.otbr.util.compute_pskc"
    ):  # Patch to speed up tests
        assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf):
    """Mock zeroconf in all tests."""


@pytest.fixture(name="multiprotocol_addon_manager_mock")
def multiprotocol_addon_manager_mock_fixture(hass: HomeAssistant):
    """Mock the Silicon Labs Multiprotocol add-on manager."""
    mock_manager = Mock()
    mock_manager.async_get_channel = Mock(return_value=None)
    with patch.dict(hass.data, {"silabs_multiprotocol_addon_manager": mock_manager}):
        yield mock_manager
