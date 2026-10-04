"""Test OTBR Websocket API."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
import python_otbr_api
from yarl import URL

from homeassistant.components import otbr, thread
from homeassistant.components.otbr import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    BASE_URL,
    DATASET_CH15,
    DATASET_CH16,
    TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    TEST_BORDER_AGENT_ID,
)

from tests.common import MockUser
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture
async def websocket_client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Create a websocket client."""
    return await hass_ws_client(hass)


@pytest.fixture(autouse=True)
def mock_supervisor_client(supervisor_client: AsyncMock) -> None:
    """Mock supervisor client."""


@pytest.mark.parametrize(
    ("ephemeral_key_probe_status", "ephemeral_key_supported"),
    [
        pytest.param(HTTPStatus.OK, True, id="supported"),
        pytest.param(HTTPStatus.NOT_FOUND, False, id="not_supported"),
    ],
)
async def test_get_info(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
    ephemeral_key_supported: bool,
) -> None:
    """Test async_get_info."""
    extended_pan_id = "ABCD1234"

    with (
        patch(
            "python_otbr_api.OTBR.get_active_dataset",
            return_value=python_otbr_api.ActiveDataSet(
                channel=16, extended_pan_id=extended_pan_id
            ),
        ),
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
        ),
        patch(
            "python_otbr_api.OTBR.get_border_agent_id",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/info"})
        msg = await websocket_client.receive_json()

    assert msg["success"]
    extended_address = TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex()
    assert msg["result"] == {
        extended_address: {
            "url": BASE_URL,
            "active_dataset_tlvs": DATASET_CH16.hex().lower(),
            "channel": 16,
            "border_agent_id": TEST_BORDER_AGENT_ID.hex(),
            "extended_address": extended_address,
            "extended_pan_id": extended_pan_id.lower(),
            "ephemeral_key_supported": ephemeral_key_supported,
        }
    }


@pytest.mark.parametrize(
    ("ephemeral_key_probe_status", "ephemeral_key_supported"),
    [
        pytest.param(HTTPStatus.OK, True, id="supported"),
        pytest.param(HTTPStatus.NOT_FOUND, False, id="not_supported"),
    ],
)
async def test_get_info_probes_ephemeral_key_support(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan: str,
    websocket_client: MockHAClientWebSocket,
    ephemeral_key_supported: bool,
) -> None:
    """Test otbr/info probes for ephemeral key support while it is unknown."""
    entry = hass.config_entries.async_get_entry(otbr_config_entry_multipan)
    assert entry is not None
    entry.runtime_data.ephemeral_key_supported = None
    probes = len([call for call in aioclient_mock.mock_calls if call[0] == "GET"])

    with (
        patch(
            "python_otbr_api.OTBR.get_active_dataset",
            return_value=python_otbr_api.ActiveDataSet(channel=16),
        ),
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
        ),
        patch(
            "python_otbr_api.OTBR.get_border_agent_id",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/info"})
        msg = await websocket_client.receive_json()
        await websocket_client.send_json_auto_id({"type": "otbr/info"})
        msg2 = await websocket_client.receive_json()

    result = msg["result"][TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex()]
    assert result["ephemeral_key_supported"] is ephemeral_key_supported
    assert msg2["result"] == msg["result"]
    # Probed once, then remembered
    assert len([call for call in aioclient_mock.mock_calls if call[0] == "GET"]) == (
        probes + 1
    )


async def test_get_info_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test async_get_info."""
    await async_setup_component(hass, DOMAIN, {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id({"type": "otbr/info"})

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_get_info_fetch_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test async_get_info."""
    with (
        patch(
            "python_otbr_api.OTBR.get_active_dataset",
            side_effect=python_otbr_api.OTBRError,
        ),
        patch(
            "python_otbr_api.OTBR.get_border_agent_id",
            return_value=TEST_BORDER_AGENT_ID,
        ),
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/info"})
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "otbr_info_failed"


async def test_create_network(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""

    with (
        patch("python_otbr_api.OTBR.create_active_dataset") as create_dataset_mock,
        patch("python_otbr_api.OTBR.factory_reset") as factory_reset_mock,
        patch("python_otbr_api.OTBR.set_enabled") as set_enabled_mock,
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
        ) as get_active_dataset_tlvs_mock,
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch(
            "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
        ) as mock_add,
        patch(
            "homeassistant.components.otbr.util.random.randint",
            return_value=0x1234,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )

        msg = await websocket_client.receive_json()
        assert msg["success"]
        assert msg["result"] is None

    create_dataset_mock.assert_called_once_with(
        python_otbr_api.models.ActiveDataSet(
            channel=15, network_name="ha-thread-1234", pan_id=0x1234
        )
    )
    factory_reset_mock.assert_called_once_with()
    assert len(set_enabled_mock.mock_calls) == 2
    assert set_enabled_mock.mock_calls[0][1][0] is False
    assert set_enabled_mock.mock_calls[1][1][0] is True
    get_active_dataset_tlvs_mock.assert_called_once()
    mock_add.assert_called_once_with(otbr.DOMAIN, DATASET_CH16.hex(), None, None)


async def test_create_network_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test create network."""
    await async_setup_component(hass, DOMAIN, {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id(
        {"type": "otbr/create_network", "extended_address": "blah"}
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_create_network_fails_1(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with (
        patch(
            "python_otbr_api.OTBR.set_enabled",
            side_effect=python_otbr_api.OTBRError,
        ),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_enabled_failed"


async def test_create_network_fails_2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with (
        patch(
            "python_otbr_api.OTBR.set_enabled",
        ),
        patch(
            "python_otbr_api.OTBR.create_active_dataset",
            side_effect=python_otbr_api.OTBRError,
        ),
        patch("python_otbr_api.OTBR.factory_reset"),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "create_active_dataset_failed"


async def test_create_network_fails_3(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with (
        patch(
            "python_otbr_api.OTBR.set_enabled",
            side_effect=[None, python_otbr_api.OTBRError],
        ),
        patch(
            "python_otbr_api.OTBR.create_active_dataset",
        ),
        patch(
            "python_otbr_api.OTBR.factory_reset",
        ),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_enabled_failed"


async def test_create_network_fails_4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with (
        patch("python_otbr_api.OTBR.set_enabled"),
        patch("python_otbr_api.OTBR.create_active_dataset"),
        patch(
            "python_otbr_api.OTBR.get_active_dataset_tlvs",
            side_effect=python_otbr_api.OTBRError,
        ),
        patch(
            "python_otbr_api.OTBR.factory_reset",
        ),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "get_active_dataset_tlvs_failed"


async def test_create_network_fails_5(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with (
        patch("python_otbr_api.OTBR.set_enabled"),
        patch("python_otbr_api.OTBR.create_active_dataset"),
        patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None),
        patch("python_otbr_api.OTBR.factory_reset"),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "get_active_dataset_tlvs_empty"


async def test_create_network_fails_6(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with (
        patch("python_otbr_api.OTBR.set_enabled"),
        patch("python_otbr_api.OTBR.create_active_dataset"),
        patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None),
        patch(
            "python_otbr_api.OTBR.factory_reset",
            side_effect=python_otbr_api.OTBRError,
        ),
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "factory_reset_failed"


async def test_create_network_fails_7(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "get_extended_address_failed"


async def test_create_network_fails_8(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test create network."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_network",
                "extended_address": "blah",
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unknown_router"


async def test_set_network(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""

    await thread.async_add_dataset(hass, "test", DATASET_CH15.hex())
    dataset_store = await thread.dataset_store.async_get_store(hass)
    dataset_id = list(dataset_store.datasets)[1]

    with (
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch(
            "python_otbr_api.OTBR.set_active_dataset_tlvs"
        ) as set_active_dataset_tlvs_mock,
        patch("python_otbr_api.OTBR.set_enabled") as set_enabled_mock,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "dataset_id": dataset_id,
            }
        )

        msg = await websocket_client.receive_json()
        assert msg["success"]
        assert msg["result"] is None

    set_active_dataset_tlvs_mock.assert_called_once_with(DATASET_CH15)
    assert len(set_enabled_mock.mock_calls) == 2
    assert set_enabled_mock.mock_calls[0][1][0] is False
    assert set_enabled_mock.mock_calls[1][1][0] is True


async def test_set_network_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test set network."""
    await async_setup_component(hass, DOMAIN, {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id(
        {
            "type": "otbr/set_network",
            "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            "dataset_id": "abc",
        }
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_set_network_channel_conflict(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    multiprotocol_addon_manager_mock,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""

    dataset_store = await thread.dataset_store.async_get_store(hass)
    dataset_id = list(dataset_store.datasets)[0]

    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "dataset_id": dataset_id,
            }
        )

        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "channel_conflict"


async def test_set_network_unknown_dataset(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "dataset_id": "abc",
            }
        )

        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unknown_dataset"


async def test_set_network_fails_1(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""
    await thread.async_add_dataset(hass, "test", DATASET_CH15.hex())
    dataset_store = await thread.dataset_store.async_get_store(hass)
    dataset_id = list(dataset_store.datasets)[1]

    with (
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch(
            "python_otbr_api.OTBR.set_enabled",
            side_effect=python_otbr_api.OTBRError,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "dataset_id": dataset_id,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_enabled_failed"


async def test_set_network_fails_2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""
    await thread.async_add_dataset(hass, "test", DATASET_CH15.hex())
    dataset_store = await thread.dataset_store.async_get_store(hass)
    dataset_id = list(dataset_store.datasets)[1]

    with (
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch(
            "python_otbr_api.OTBR.set_enabled",
        ),
        patch(
            "python_otbr_api.OTBR.set_active_dataset_tlvs",
            side_effect=python_otbr_api.OTBRError,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "dataset_id": dataset_id,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_active_dataset_tlvs_failed"


async def test_set_network_fails_3(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""
    await thread.async_add_dataset(hass, "test", DATASET_CH15.hex())
    dataset_store = await thread.dataset_store.async_get_store(hass)
    dataset_id = list(dataset_store.datasets)[1]

    with (
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch(
            "python_otbr_api.OTBR.set_enabled",
            side_effect=[None, python_otbr_api.OTBRError],
        ),
        patch(
            "python_otbr_api.OTBR.set_active_dataset_tlvs",
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "dataset_id": dataset_id,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_enabled_failed"


async def test_set_network_fails_4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "dataset_id": "abc",
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "get_extended_address_failed"


async def test_set_network_fails_5(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set network."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
                "extended_address": "blah",
                "dataset_id": "abc",
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unknown_router"


async def test_set_channel(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_thread,
    websocket_client,
) -> None:
    """Test set channel."""

    with (
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch("python_otbr_api.OTBR.set_channel"),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_channel",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "channel": 12,
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"delay": 300.0}


async def test_set_channel_multiprotocol(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set channel."""

    with (
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch("python_otbr_api.OTBR.set_channel"),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_channel",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "channel": 12,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "multiprotocol_enabled"


async def test_set_channel_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test set channel."""
    await async_setup_component(hass, DOMAIN, {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id(
        {
            "type": "otbr/set_channel",
            "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            "channel": 12,
        }
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_set_channel_fails_1(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_thread,
    websocket_client,
) -> None:
    """Test set channel."""
    with (
        patch(
            "python_otbr_api.OTBR.get_extended_address",
            return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
        ),
        patch(
            "python_otbr_api.OTBR.set_channel",
            side_effect=python_otbr_api.OTBRError,
        ),
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_channel",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "channel": 12,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_channel_failed"


async def test_set_channel_fails_2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set channel."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_channel",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "channel": 12,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "get_extended_address_failed"


async def test_set_channel_fails_3(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test set channel."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_channel",
                "extended_address": "blah",
                "channel": 12,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unknown_router"


EPHEMERAL_KEY_COMMANDS = [
    pytest.param("otbr/create_ephemeral_key", id="create"),
    pytest.param("otbr/delete_ephemeral_key", id="delete"),
]


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test create ephemeral key activates the key on the border router."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state")
    aioclient_mock.post(
        f"{BASE_URL}/node/ba-epskc/key", json={"tap": "700855744", "port": 49154}
    )

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "ephemeral_key": "700855744",
        "lifetime": 300,
        "port": 49154,
    }
    # The feature is enabled first; the border agent API takes the lifetime in ms
    assert aioclient_mock.mock_calls[-2][2] == "enable"
    assert aioclient_mock.mock_calls[-1][2] == {"lifetime": 300000}


@pytest.mark.parametrize(
    ("state_status", "key_status"),
    [
        pytest.param(HTTPStatus.NOT_FOUND, HTTPStatus.OK, id="state_not_found"),
        pytest.param(HTTPStatus.OK, HTTPStatus.NOT_FOUND, id="key_not_found"),
        # Routers which reject the method before matching the path answer 405
        pytest.param(
            HTTPStatus.METHOD_NOT_ALLOWED, HTTPStatus.OK, id="state_not_allowed"
        ),
        pytest.param(
            HTTPStatus.OK, HTTPStatus.METHOD_NOT_ALLOWED, id="key_not_allowed"
        ),
    ],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key_not_supported(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    state_status: HTTPStatus,
    key_status: HTTPStatus,
) -> None:
    """Test a router without ephemeral key support is reported as unsupported."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state", status=state_status)
    aioclient_mock.post(f"{BASE_URL}/node/ba-epskc/key", status=key_status, json={})

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "ephemeral_key_not_supported"


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key_replaces_active_key(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test an unused active key is dropped so a new one can be created."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state")
    aioclient_mock.get(
        f"{BASE_URL}/node/ba-epskc/key", json={"state": "started", "port": 49154}
    )
    aioclient_mock.delete(f"{BASE_URL}/node/ba-epskc/key")
    # The border router only accepts a new key from the stopped state, so the
    # first activation conflicts and only the one after the delete succeeds
    responses = [
        AiohttpClientMockResponse(
            "POST", URL(f"{BASE_URL}/node/ba-epskc/key"), status=HTTPStatus.CONFLICT
        ),
        AiohttpClientMockResponse(
            "POST",
            URL(f"{BASE_URL}/node/ba-epskc/key"),
            json={"tap": "700855744", "port": 49154},
        ),
    ]

    async def activate(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        return responses.pop(0)

    aioclient_mock.post(f"{BASE_URL}/node/ba-epskc/key", side_effect=activate)

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["success"]
    assert msg["result"]["ephemeral_key"] == "700855744"
    assert [call[0] for call in aioclient_mock.mock_calls[-5:]] == [
        "PUT",
        "POST",
        "GET",
        "DELETE",
        "POST",
    ]


@pytest.mark.parametrize(
    ("elapsed", "success"),
    [
        pytest.param(timedelta(minutes=1), False, id="key_still_valid"),
        pytest.param(timedelta(minutes=6), True, id="key_expired"),
    ],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key_twice(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    freezer: FrozenDateTimeFactory,
    elapsed: timedelta,
    success: bool,
) -> None:
    """Test a key handed out by this instance is not replaced until it expires."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state")
    aioclient_mock.post(
        f"{BASE_URL}/node/ba-epskc/key", json={"tap": "700855744", "port": 49154}
    )

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        assert (await websocket_client.receive_json())["success"]
        posts = aioclient_mock.call_count
        freezer.tick(elapsed)
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["success"] is success
    assert msg.get("error", {}).get("code") == (
        None if success else "ephemeral_key_in_use"
    )
    # The router is only asked for another key once the first one has expired
    assert (aioclient_mock.call_count > posts) is success


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key_concurrently(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test only one of two concurrent requests gets a key."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state")
    release = asyncio.Event()
    requests: asyncio.Queue[None] = asyncio.Queue()

    async def activate(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        await release.wait()
        return AiohttpClientMockResponse(
            "POST",
            URL(f"{BASE_URL}/node/ba-epskc/key"),
            json={"tap": "700855744", "port": 49154},
        )

    async def get_extended_address() -> bytes:
        # Called by each request right before the ephemeral key lock
        await requests.put(None)
        return TEST_BORDER_AGENT_EXTENDED_ADDRESS

    aioclient_mock.post(f"{BASE_URL}/node/ba-epskc/key", side_effect=activate)
    create_msg = {
        "type": "otbr/create_ephemeral_key",
        "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
    }

    with patch(
        "python_otbr_api.OTBR.get_extended_address", side_effect=get_extended_address
    ):
        await websocket_client.send_json_auto_id(create_msg)
        await requests.get()
        await websocket_client.send_json_auto_id(create_msg)
        await requests.get()
        # Both requests are in flight: the first waits on the router, the
        # second must be waiting for the first to finish
        release.set()
        msgs = [
            await websocket_client.receive_json(),
            await websocket_client.receive_json(),
        ]

    assert sorted(msg.get("error", {}).get("code", "success") for msg in msgs) == [
        "ephemeral_key_in_use",
        "success",
    ]
    # The router was only asked for one key
    assert len([call for call in aioclient_mock.mock_calls if call[0] == "POST"]) == 1


@pytest.mark.parametrize("state", ["connected", "accepted"])
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key_in_use(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    state: str,
) -> None:
    """Test a key a device is joining through is not replaced."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state")
    aioclient_mock.post(f"{BASE_URL}/node/ba-epskc/key", status=HTTPStatus.CONFLICT)
    aioclient_mock.get(
        f"{BASE_URL}/node/ba-epskc/key", json={"state": state, "port": 49154}
    )

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "ephemeral_key_in_use"
    assert not any(call[0] == "DELETE" for call in aioclient_mock.mock_calls)


KEY_STARTED = (HTTPStatus.OK, {"state": "started", "port": 49154})


@pytest.mark.parametrize(
    ("state_status", "key_responses", "key_status", "delete_status"),
    [
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            [],
            KEY_STARTED,
            HTTPStatus.OK,
            id="enable_fails",
        ),
        pytest.param(
            HTTPStatus.OK,
            [(HTTPStatus.INTERNAL_SERVER_ERROR, None)],
            KEY_STARTED,
            HTTPStatus.OK,
            id="activate_fails",
        ),
        pytest.param(
            HTTPStatus.OK,
            [(HTTPStatus.OK, {"tap": "700855744"})],
            KEY_STARTED,
            HTTPStatus.OK,
            id="missing_port",
        ),
        pytest.param(
            HTTPStatus.OK,
            [(HTTPStatus.OK, [])],
            KEY_STARTED,
            HTTPStatus.OK,
            id="not_a_dict",
        ),
        pytest.param(
            HTTPStatus.OK,
            [(HTTPStatus.CONFLICT, None), (HTTPStatus.CONFLICT, None)],
            KEY_STARTED,
            HTTPStatus.OK,
            id="conflict_after_replacement",
        ),
        pytest.param(
            HTTPStatus.OK,
            [(HTTPStatus.CONFLICT, None)],
            (HTTPStatus.INTERNAL_SERVER_ERROR, None),
            HTTPStatus.OK,
            id="key_status_fails",
        ),
        pytest.param(
            HTTPStatus.OK,
            [(HTTPStatus.CONFLICT, None)],
            (HTTPStatus.OK, {"port": 49154}),
            HTTPStatus.OK,
            id="key_status_missing_state",
        ),
        pytest.param(
            HTTPStatus.OK,
            [(HTTPStatus.CONFLICT, None)],
            KEY_STARTED,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            id="delete_fails",
        ),
    ],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key_fails(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    state_status: HTTPStatus,
    key_responses: list[tuple[HTTPStatus, Any]],
    key_status: tuple[HTTPStatus, Any],
    delete_status: HTTPStatus,
) -> None:
    """Test create ephemeral key when the border router returns an error."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state", status=state_status)
    aioclient_mock.get(
        f"{BASE_URL}/node/ba-epskc/key", status=key_status[0], json=key_status[1]
    )
    aioclient_mock.delete(f"{BASE_URL}/node/ba-epskc/key", status=delete_status)
    responses = [
        AiohttpClientMockResponse(
            "POST", URL(f"{BASE_URL}/node/ba-epskc/key"), status=status, json=json
        )
        for status, json in key_responses
    ]

    async def activate(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        return responses.pop(0)

    aioclient_mock.post(f"{BASE_URL}/node/ba-epskc/key", side_effect=activate)

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "create_ephemeral_key_failed"
    # Every scripted activation response was consumed and no extra one requested
    assert not responses


@pytest.mark.parametrize("error", [aiohttp.ClientError, TimeoutError])
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_create_ephemeral_key_connection_error(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    error: type[Exception],
) -> None:
    """Test create ephemeral key when the border router cannot be reached."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state", exc=error)

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "create_ephemeral_key_failed"


@pytest.mark.parametrize("command", EPHEMERAL_KEY_COMMANDS)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_ephemeral_key_not_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    command: str,
) -> None:
    """Test ephemeral key commands require an admin user."""
    hass_admin_user.groups = []
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id(
        {
            "type": command,
            "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
        }
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("command", EPHEMERAL_KEY_COMMANDS)
async def test_ephemeral_key_no_entry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    command: str,
) -> None:
    """Test ephemeral key commands without a loaded config entry."""
    await async_setup_component(hass, DOMAIN, {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id(
        {
            "type": command,
            "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
        }
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


@pytest.mark.parametrize("command", EPHEMERAL_KEY_COMMANDS)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_ephemeral_key_unknown_router(
    websocket_client: MockHAClientWebSocket,
    command: str,
) -> None:
    """Test ephemeral key commands for an unknown router."""
    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": command,
                "extended_address": "blah",
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unknown_router"


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_delete_ephemeral_key(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test delete ephemeral key deactivates the key on the border router."""
    aioclient_mock.delete(f"{BASE_URL}/node/ba-epskc/key")

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/delete_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["success"]
    assert msg["result"] is None
    assert aioclient_mock.mock_calls[-1][0] == "DELETE"


@pytest.mark.parametrize(
    ("ephemeral_key", "elapsed", "deleted"),
    [
        pytest.param("700855744", timedelta(minutes=1), True, id="active_key"),
        pytest.param("123456789", timedelta(minutes=1), False, id="replaced_key"),
        pytest.param("700855744", timedelta(minutes=6), False, id="expired_key"),
    ],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_delete_ephemeral_key_by_key(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    freezer: FrozenDateTimeFactory,
    ephemeral_key: str,
    elapsed: timedelta,
    deleted: bool,
) -> None:
    """Test deleting a specific key only deactivates it if it is still active."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state")
    aioclient_mock.post(
        f"{BASE_URL}/node/ba-epskc/key", json={"tap": "700855744", "port": 49154}
    )
    aioclient_mock.delete(f"{BASE_URL}/node/ba-epskc/key")

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        assert (await websocket_client.receive_json())["success"]
        freezer.tick(elapsed)
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/delete_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
                "ephemeral_key": ephemeral_key,
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["success"]
    assert any(call[0] == "DELETE" for call in aioclient_mock.mock_calls) is deleted


@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_delete_ephemeral_key_retry_after_failure(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test a key is still known after a failed delete, so a retry deletes it."""
    aioclient_mock.put(f"{BASE_URL}/node/ba-epskc/state")
    aioclient_mock.post(
        f"{BASE_URL}/node/ba-epskc/key", json={"tap": "700855744", "port": 49154}
    )
    responses = [
        AiohttpClientMockResponse(
            "DELETE",
            URL(f"{BASE_URL}/node/ba-epskc/key"),
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        ),
        AiohttpClientMockResponse("DELETE", URL(f"{BASE_URL}/node/ba-epskc/key")),
    ]

    async def delete(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        return responses.pop(0)

    aioclient_mock.delete(f"{BASE_URL}/node/ba-epskc/key", side_effect=delete)
    delete_msg = {
        "type": "otbr/delete_ephemeral_key",
        "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
        "ephemeral_key": "700855744",
    }

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/create_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        assert (await websocket_client.receive_json())["success"]
        await websocket_client.send_json_auto_id(delete_msg)
        failed = await websocket_client.receive_json()
        await websocket_client.send_json_auto_id(delete_msg)
        retried = await websocket_client.receive_json()

    assert not failed["success"]
    assert failed["error"]["code"] == "delete_ephemeral_key_failed"
    assert retried["success"]
    # Both attempts reached the router
    assert not responses


@pytest.mark.parametrize("error", [aiohttp.ClientError, TimeoutError])
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_delete_ephemeral_key_connection_error(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    error: type[Exception],
) -> None:
    """Test delete ephemeral key when the border router cannot be reached."""
    aioclient_mock.delete(f"{BASE_URL}/node/ba-epskc/key", exc=error)

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/delete_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "delete_ephemeral_key_failed"


@pytest.mark.parametrize(
    ("delete_status", "error_code"),
    [
        pytest.param(
            HTTPStatus.NOT_FOUND, "ephemeral_key_not_supported", id="not_found"
        ),
        # Routers which reject the method before matching the path answer 405
        pytest.param(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "ephemeral_key_not_supported",
            id="not_allowed",
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "delete_ephemeral_key_failed",
            id="error",
        ),
    ],
)
@pytest.mark.usefixtures("otbr_config_entry_multipan")
async def test_delete_ephemeral_key_fails(
    aioclient_mock: AiohttpClientMocker,
    websocket_client: MockHAClientWebSocket,
    delete_status: HTTPStatus,
    error_code: str,
) -> None:
    """Test delete ephemeral key when the border router returns an error."""
    aioclient_mock.delete(f"{BASE_URL}/node/ba-epskc/key", status=delete_status)

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/delete_ephemeral_key",
                "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == error_code
