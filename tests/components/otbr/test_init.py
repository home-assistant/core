"""Test the Open Thread Border Router integration."""
import asyncio
from http import HTTPStatus
from unittest.mock import patch

import aiohttp
import pytest
import python_otbr_api

from homeassistant.components import otbr
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from . import (
    BASE_URL,
    CONFIG_ENTRY_DATA,
    DATASET_CH16,
    DATASET_INSECURE_NW_KEY,
    DATASET_INSECURE_PASSPHRASE,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_import_dataset(hass: HomeAssistant) -> None:
    """Test the active dataset is imported at setup."""
    issue_registry = ir.async_get(hass)

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
    ) as mock_add:
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    mock_add.assert_called_once_with(config_entry.title, DATASET_CH16.hex())
    assert not issue_registry.async_get_issue(
        domain=otbr.DOMAIN, issue_id=f"insecure_thread_network_{config_entry.entry_id}"
    )


@pytest.mark.parametrize(
    "dataset", [DATASET_INSECURE_NW_KEY, DATASET_INSECURE_PASSPHRASE]
)
async def test_import_insecure_dataset(hass: HomeAssistant, dataset: bytes) -> None:
    """Test the active dataset is imported at setup.

    This imports a dataset with insecure settings.
    """
    issue_registry = ir.async_get(hass)

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=dataset
    ), patch(
        "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
    ) as mock_add:
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    mock_add.assert_called_once_with(config_entry.title, dataset.hex())
    assert issue_registry.async_get_issue(
        domain=otbr.DOMAIN, issue_id=f"insecure_thread_network_{config_entry.entry_id}"
    )


@pytest.mark.parametrize(
    "error",
    [
        asyncio.TimeoutError,
        python_otbr_api.OTBRError,
        aiohttp.ClientError,
    ],
)
async def test_config_entry_not_ready(hass: HomeAssistant, error) -> None:
    """Test raising ConfigEntryNotReady ."""

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch("python_otbr_api.OTBR.get_active_dataset_tlvs", side_effect=error):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)


async def test_remove_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry
) -> None:
    """Test async_get_active_dataset_tlvs after removing the config entry."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text="0E")

    assert await otbr.async_get_active_dataset_tlvs(hass) == bytes.fromhex("0E")

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    await hass.config_entries.async_remove(config_entry.entry_id)

    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry
) -> None:
    """Test async_get_active_dataset_tlvs."""

    mock_response = (
        "0E080000000000010000000300001035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
        "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
        "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
    )

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text=mock_response)

    assert await otbr.async_get_active_dataset_tlvs(hass) == bytes.fromhex(
        mock_response
    )


async def test_get_active_dataset_tlvs_empty(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry
) -> None:
    """Test async_get_active_dataset_tlvs."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    assert await otbr.async_get_active_dataset_tlvs(hass) is None


async def test_get_active_dataset_tlvs_addon_not_installed(hass: HomeAssistant) -> None:
    """Test async_get_active_dataset_tlvs when the multi-PAN addon is not installed."""

    with pytest.raises(HomeAssistantError):
        await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry
) -> None:
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NOT_FOUND)
    with pytest.raises(HomeAssistantError):
        await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs_201(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry
) -> None:
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.CREATED)
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry
) -> None:
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text="unexpected")
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass)
