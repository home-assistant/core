"""Test the Open Thread Border Router integration."""
import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import aiohttp
import pytest
import python_otbr_api
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components import otbr, thread
from homeassistant.components.thread import discovery
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import (
    BASE_URL,
    CONFIG_ENTRY_DATA_MULTIPAN,
    CONFIG_ENTRY_DATA_THREAD,
    DATASET_CH15,
    DATASET_CH16,
    DATASET_INSECURE_NW_KEY,
    DATASET_INSECURE_PASSPHRASE,
    ROUTER_DISCOVERY_HASS,
    TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    TEST_BORDER_AGENT_ID,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

DATASET_NO_CHANNEL = bytes.fromhex(
    "0E08000000000001000035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
    "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
    "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
)


async def test_import_dataset(hass: HomeAssistant, mock_async_zeroconf: None) -> None:
    """Test the active dataset is imported at setup."""
    add_service_listener_called = asyncio.Event()

    async def mock_add_service_listener(type_: str, listener: Any):
        add_service_listener_called.set()

    mock_async_zeroconf.async_add_service_listener = AsyncMock(
        side_effect=mock_add_service_listener
    )
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    issue_registry = ir.async_get(hass)
    assert await thread.async_get_preferred_dataset(hass) is None

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "python_otbr_api.OTBR.get_border_agent_id", return_value=TEST_BORDER_AGENT_ID
    ), patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ), patch(
        "homeassistant.components.thread.dataset_store.BORDER_AGENT_DISCOVERY_TIMEOUT",
        0.1,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        # Wait for Thread router discovery to start
        await add_service_listener_called.wait()
        mock_async_zeroconf.async_add_service_listener.assert_called_once_with(
            "_meshcop._udp.local.", ANY
        )

        # Discover a service matching our router
        listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
            mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
        )
        mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
            **ROUTER_DISCOVERY_HASS
        )
        listener.add_service(
            None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
        )

        # Wait for discovery of other routers to time out
        await hass.async_block_till_done()

    dataset_store = await thread.dataset_store.async_get_store(hass)
    assert (
        list(dataset_store.datasets.values())[0].preferred_border_agent_id
        == TEST_BORDER_AGENT_ID.hex()
    )
    assert (
        list(dataset_store.datasets.values())[0].preferred_extended_address
        == TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex()
    )
    assert await thread.async_get_preferred_dataset(hass) == DATASET_CH16.hex()
    assert not issue_registry.async_get_issue(
        domain=otbr.DOMAIN, issue_id=f"insecure_thread_network_{config_entry.entry_id}"
    )
    assert not issue_registry.async_get_issue(
        domain=otbr.DOMAIN,
        issue_id=f"otbr_zha_channel_collision_{config_entry.entry_id}",
    )


async def test_import_share_radio_channel_collision(
    hass: HomeAssistant, multiprotocol_addon_manager_mock
) -> None:
    """Test the active dataset is imported at setup.

    This imports a dataset with different channel than ZHA when ZHA and OTBR share
    the radio.
    """
    issue_registry = ir.async_get(hass)

    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "python_otbr_api.OTBR.get_border_agent_id", return_value=TEST_BORDER_AGENT_ID
    ), patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ), patch(
        "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
    ) as mock_add:
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    mock_add.assert_called_once_with(
        otbr.DOMAIN,
        DATASET_CH16.hex(),
        TEST_BORDER_AGENT_ID.hex(),
        TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
    )
    assert issue_registry.async_get_issue(
        domain=otbr.DOMAIN,
        issue_id=f"otbr_zha_channel_collision_{config_entry.entry_id}",
    )


@pytest.mark.parametrize("dataset", [DATASET_CH15, DATASET_NO_CHANNEL])
async def test_import_share_radio_no_channel_collision(
    hass: HomeAssistant, multiprotocol_addon_manager_mock, dataset: bytes
) -> None:
    """Test the active dataset is imported at setup.

    This imports a dataset when ZHA and OTBR share the radio.
    """
    issue_registry = ir.async_get(hass)

    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=dataset
    ), patch(
        "python_otbr_api.OTBR.get_border_agent_id", return_value=TEST_BORDER_AGENT_ID
    ), patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ), patch(
        "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
    ) as mock_add:
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    mock_add.assert_called_once_with(
        otbr.DOMAIN,
        dataset.hex(),
        TEST_BORDER_AGENT_ID.hex(),
        TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
    )
    assert not issue_registry.async_get_issue(
        domain=otbr.DOMAIN,
        issue_id=f"otbr_zha_channel_collision_{config_entry.entry_id}",
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
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=dataset
    ), patch(
        "python_otbr_api.OTBR.get_border_agent_id", return_value=TEST_BORDER_AGENT_ID
    ), patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ), patch(
        "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
    ) as mock_add:
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    mock_add.assert_called_once_with(
        otbr.DOMAIN,
        dataset.hex(),
        TEST_BORDER_AGENT_ID.hex(),
        TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
    )
    assert issue_registry.async_get_issue(
        domain=otbr.DOMAIN, issue_id=f"insecure_thread_network_{config_entry.entry_id}"
    )


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError,
        python_otbr_api.OTBRError,
        aiohttp.ClientError,
    ],
)
async def test_config_entry_not_ready(hass: HomeAssistant, error) -> None:
    """Test raising ConfigEntryNotReady ."""

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch("python_otbr_api.OTBR.get_active_dataset_tlvs", side_effect=error):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)


async def test_border_agent_id_not_supported(hass: HomeAssistant) -> None:
    """Test border router does not support border agent ID."""

    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "python_otbr_api.OTBR.get_border_agent_id",
        side_effect=python_otbr_api.GetBorderAgentIdNotSupportedError,
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)


async def test_config_entry_update(hass: HomeAssistant) -> None:
    """Test update config entry settings."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="My OTBR",
    )
    config_entry.add_to_hass(hass)
    mock_api = MagicMock()
    mock_api.get_active_dataset_tlvs = AsyncMock(return_value=None)
    mock_api.get_border_agent_id = AsyncMock(return_value=TEST_BORDER_AGENT_ID)
    mock_api.get_extended_address = AsyncMock(
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS
    )
    with patch("python_otbr_api.OTBR", return_value=mock_api) as mock_otrb_api:
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    mock_otrb_api.assert_called_once_with(CONFIG_ENTRY_DATA_MULTIPAN["url"], ANY, ANY)

    new_config_entry_data = {"url": "http://core-silabs-multiprotocol:8082"}
    assert CONFIG_ENTRY_DATA_MULTIPAN["url"] != new_config_entry_data["url"]
    with patch("python_otbr_api.OTBR", return_value=mock_api) as mock_otrb_api:
        hass.config_entries.async_update_entry(config_entry, data=new_config_entry_data)
        await hass.async_block_till_done()

    mock_otrb_api.assert_called_once_with(new_config_entry_data["url"], ANY, ANY)


async def test_remove_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry_multipan
) -> None:
    """Test async_get_active_dataset_tlvs after removing the config entry."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text="0E")

    assert await otbr.async_get_active_dataset_tlvs(hass) == bytes.fromhex("0E")

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    await hass.config_entries.async_remove(config_entry.entry_id)

    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry_multipan
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
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry_multipan
) -> None:
    """Test async_get_active_dataset_tlvs."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    assert await otbr.async_get_active_dataset_tlvs(hass) is None


async def test_get_active_dataset_tlvs_addon_not_installed(hass: HomeAssistant) -> None:
    """Test async_get_active_dataset_tlvs when the multi-PAN addon is not installed."""

    with pytest.raises(HomeAssistantError):
        await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry_multipan
) -> None:
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NOT_FOUND)
    with pytest.raises(HomeAssistantError):
        await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs_201(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry_multipan
) -> None:
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.CREATED)
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass)


async def test_get_active_dataset_tlvs_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_config_entry_multipan
) -> None:
    """Test async_get_active_dataset_tlvs with error."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text="unexpected")
    with pytest.raises(HomeAssistantError):
        assert await otbr.async_get_active_dataset_tlvs(hass)


async def test_remove_extra_entries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we remove additional config entries."""

    config_entry1 = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_MULTIPAN,
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
    )
    config_entry2 = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_THREAD,
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
    )
    config_entry1.add_to_hass(hass)
    config_entry2.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 2
    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ), patch(
        "homeassistant.components.otbr.util.compute_pskc"
    ):  # Patch to speed up tests
        assert await async_setup_component(hass, otbr.DOMAIN, {})
    assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 1
