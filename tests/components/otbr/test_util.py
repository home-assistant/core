"""Test OTBR Utility functions."""

from unittest.mock import AsyncMock, patch

import pytest
import python_otbr_api

from homeassistant.components import otbr
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

OTBR_MULTIPAN_URL = "http://core-silabs-multiprotocol:8081"
OTBR_NON_MULTIPAN_URL = "/dev/ttyAMA1"


@pytest.fixture(autouse=True)
def mock_supervisor_client(supervisor_client: AsyncMock) -> None:
    """Mock supervisor client."""


async def test_get_allowed_channel(
    hass: HomeAssistant, multiprotocol_addon_manager_mock
) -> None:
    """Test get_allowed_channel."""

    # OTBR multipan + No configured channel -> no restriction
    multiprotocol_addon_manager_mock.async_get_channel.return_value = None
    assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) is None

    # OTBR multipan + multipan using channel 15 -> 15
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15
    assert await otbr.util.get_allowed_channel(hass, OTBR_MULTIPAN_URL) == 15

    # OTBR no multipan + multipan using channel 15 -> no restriction
    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15
    assert await otbr.util.get_allowed_channel(hass, OTBR_NON_MULTIPAN_URL) is None


async def test_factory_reset(
    hass: HomeAssistant,
    otbr_config_entry_multipan: str,
    get_border_agent_id: AsyncMock,
) -> None:
    """Test factory_reset."""
    new_ba_id = b"new_ba_id"
    get_border_agent_id.return_value = new_ba_id
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert config_entry.unique_id != new_ba_id.hex()
    with (
        patch("python_otbr_api.OTBR.factory_reset") as factory_reset_mock,
        patch(
            "python_otbr_api.OTBR.delete_active_dataset"
        ) as delete_active_dataset_mock,
    ):
        await config_entry.runtime_data.factory_reset(hass)

    delete_active_dataset_mock.assert_not_called()
    factory_reset_mock.assert_called_once_with()

    # Check the unique_id is updated
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert config_entry.unique_id == new_ba_id.hex()


async def test_factory_reset_not_supported(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """Test factory_reset."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    with (
        patch(
            "python_otbr_api.OTBR.factory_reset",
            side_effect=python_otbr_api.FactoryResetNotSupportedError,
        ) as factory_reset_mock,
        patch(
            "python_otbr_api.OTBR.delete_active_dataset"
        ) as delete_active_dataset_mock,
    ):
        await config_entry.runtime_data.factory_reset(hass)

    delete_active_dataset_mock.assert_called_once_with()
    factory_reset_mock.assert_called_once_with()


async def test_factory_reset_error_1(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """Test factory_reset."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    with (
        patch(
            "python_otbr_api.OTBR.factory_reset",
            side_effect=python_otbr_api.OTBRError,
        ) as factory_reset_mock,
        patch(
            "python_otbr_api.OTBR.delete_active_dataset"
        ) as delete_active_dataset_mock,
        pytest.raises(
            HomeAssistantError,
        ),
    ):
        await config_entry.runtime_data.factory_reset(hass)

    delete_active_dataset_mock.assert_not_called()
    factory_reset_mock.assert_called_once_with()


async def test_factory_reset_error_2(
    hass: HomeAssistant, otbr_config_entry_multipan: str
) -> None:
    """Test factory_reset."""
    config_entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    with (
        patch(
            "python_otbr_api.OTBR.factory_reset",
            side_effect=python_otbr_api.FactoryResetNotSupportedError,
        ) as factory_reset_mock,
        patch(
            "python_otbr_api.OTBR.delete_active_dataset",
            side_effect=python_otbr_api.OTBRError,
        ) as delete_active_dataset_mock,
        pytest.raises(
            HomeAssistantError,
        ),
    ):
        await config_entry.runtime_data.factory_reset(hass)

    delete_active_dataset_mock.assert_called_once_with()
    factory_reset_mock.assert_called_once_with()
