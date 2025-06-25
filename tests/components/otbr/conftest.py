"""Test fixtures for the Open Thread Border Router integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components import otbr
from homeassistant.core import HomeAssistant

from . import (
    CONFIG_ENTRY_DATA_MULTIPAN,
    CONFIG_ENTRY_DATA_THREAD,
    DATASET_CH16,
    TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    TEST_BORDER_AGENT_ID,
    TEST_COPROCESSOR_VERSION,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="enable_compute_pskc")
def enable_compute_pskc_fixture() -> Any:
    """Allow controlling if compute_pskc should be enabled."""
    return False


@pytest.fixture(name="compute_pskc", autouse=True)
def compute_pskc_fixture(enable_compute_pskc: bool) -> Any:
    """Patch homeassistant.components.otbr.util.compute_pskc."""
    compute_pskc = otbr.util.compute_pskc if enable_compute_pskc else None

    with patch(
        "homeassistant.components.otbr.util.compute_pskc", side_effect=compute_pskc
    ) as compute_pskc_mock:
        yield compute_pskc_mock


@pytest.fixture(name="dataset")
def dataset_fixture() -> Any:
    """Return the discovery info from the supervisor."""
    return DATASET_CH16


@pytest.fixture(name="get_active_dataset_tlvs")
def get_active_dataset_tlvs_fixture(dataset: Any) -> Generator[AsyncMock]:
    """Mock get_active_dataset_tlvs."""
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=dataset
    ) as get_active_dataset_tlvs:
        yield get_active_dataset_tlvs


@pytest.fixture(name="get_border_agent_id")
def get_border_agent_id_fixture() -> Generator[AsyncMock]:
    """Mock get_border_agent_id."""
    with patch(
        "python_otbr_api.OTBR.get_border_agent_id", return_value=TEST_BORDER_AGENT_ID
    ) as get_border_agent_id:
        yield get_border_agent_id


@pytest.fixture(name="get_extended_address")
def get_extended_address_fixture() -> Generator[AsyncMock]:
    """Mock get_extended_address."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ) as get_extended_address:
        yield get_extended_address


@pytest.fixture(name="get_coprocessor_version")
def get_coprocessor_version_fixture() -> Generator[AsyncMock]:
    """Mock get_coprocessor_version."""
    with patch(
        "python_otbr_api.OTBR.get_coprocessor_version",
        return_value=TEST_COPROCESSOR_VERSION,
    ) as get_coprocessor_version:
        yield get_coprocessor_version


@pytest.fixture(name="otbr_config_entry_multipan")
async def otbr_config_entry_multipan_fixture(
    hass: HomeAssistant,
    get_active_dataset_tlvs: AsyncMock,
    get_border_agent_id: AsyncMock,
    get_extended_address: AsyncMock,
    get_coprocessor_version: AsyncMock,
) -> str:
    """Mock Open Thread Border Router config entry."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
        unique_id=TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    return config_entry.entry_id


@pytest.fixture(name="otbr_config_entry_thread")
async def otbr_config_entry_thread_fixture(
    hass: HomeAssistant,
    get_active_dataset_tlvs: AsyncMock,
    get_border_agent_id: AsyncMock,
    get_extended_address: AsyncMock,
    get_coprocessor_version: AsyncMock,
) -> None:
    """Mock Open Thread Border Router config entry."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_THREAD,
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
        unique_id=TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf in all tests."""


@pytest.fixture(name="multiprotocol_addon_manager_mock")
def multiprotocol_addon_manager_mock_fixture(hass: HomeAssistant):
    """Mock the Silicon Labs Multiprotocol add-on manager."""
    mock_manager = Mock()
    mock_manager.async_get_channel = Mock(return_value=None)
    with patch.dict(hass.data, {"silabs_multiprotocol_addon_manager": mock_manager}):
        yield mock_manager
