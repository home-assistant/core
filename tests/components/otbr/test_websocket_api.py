"""Test OTBR Websocket API."""

from unittest.mock import patch

import pytest
import python_otbr_api

from homeassistant.components import otbr, thread
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    BASE_URL,
    DATASET_CH15,
    DATASET_CH16,
    TEST_BORDER_AGENT_EXTENDED_ADDRESS,
    TEST_BORDER_AGENT_ID,
)

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture
async def websocket_client(hass, hass_ws_client):
    """Create a websocket client."""
    return await hass_ws_client(hass)


async def test_get_info(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_multipan,
    websocket_client,
) -> None:
    """Test async_get_info."""

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

    assert msg["success"]
    assert msg["result"] == {
        "url": BASE_URL,
        "active_dataset_tlvs": DATASET_CH16.hex().lower(),
        "channel": 16,
        "border_agent_id": TEST_BORDER_AGENT_ID.hex(),
        "extended_address": TEST_BORDER_AGENT_EXTENDED_ADDRESS.hex(),
    }


async def test_get_info_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test async_get_info."""
    await async_setup_component(hass, "otbr", {})
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
            "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
        ) as mock_add,
        patch(
            "homeassistant.components.otbr.util.random.randint",
            return_value=0x1234,
        ),
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/create_network"})

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
    await async_setup_component(hass, "otbr", {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id({"type": "otbr/create_network"})

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
    with patch(
        "python_otbr_api.OTBR.set_enabled",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/create_network"})
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
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/create_network"})
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
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/create_network"})
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
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/create_network"})
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
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/create_network"})
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
    ):
        await websocket_client.send_json_auto_id({"type": "otbr/create_network"})
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "factory_reset_failed"


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
            "python_otbr_api.OTBR.set_active_dataset_tlvs"
        ) as set_active_dataset_tlvs_mock,
        patch("python_otbr_api.OTBR.set_enabled") as set_enabled_mock,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
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
    await async_setup_component(hass, "otbr", {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id(
        {
            "type": "otbr/set_network",
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

    await websocket_client.send_json_auto_id(
        {
            "type": "otbr/set_network",
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

    await websocket_client.send_json_auto_id(
        {
            "type": "otbr/set_network",
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

    with patch(
        "python_otbr_api.OTBR.set_enabled",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "otbr/set_network",
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
                "dataset_id": dataset_id,
            }
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_enabled_failed"


async def test_set_channel(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_thread,
    websocket_client,
) -> None:
    """Test set channel."""

    with patch("python_otbr_api.OTBR.set_channel"):
        await websocket_client.send_json_auto_id(
            {"type": "otbr/set_channel", "channel": 12}
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

    with patch("python_otbr_api.OTBR.set_channel"):
        await websocket_client.send_json_auto_id(
            {"type": "otbr/set_channel", "channel": 12}
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
    await async_setup_component(hass, "otbr", {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json_auto_id(
        {"type": "otbr/set_channel", "channel": 12}
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_set_channel_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry_thread,
    websocket_client,
) -> None:
    """Test set channel."""
    with patch(
        "python_otbr_api.OTBR.set_channel",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json_auto_id(
            {"type": "otbr/set_channel", "channel": 12}
        )
        msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "set_channel_failed"
