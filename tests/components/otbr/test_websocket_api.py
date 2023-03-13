"""Test OTBR Websocket API."""
from unittest.mock import patch

import pytest
import python_otbr_api

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import BASE_URL, DATASET_CH16

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture
async def websocket_client(hass, hass_ws_client):
    """Create a websocket client."""
    return await hass_ws_client(hass)


async def test_get_info(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test async_get_info."""

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text=DATASET_CH16.hex())

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "otbr/info",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == {
        "url": BASE_URL,
        "active_dataset_tlvs": DATASET_CH16.hex().lower(),
    }


async def test_get_info_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test async_get_info."""
    await async_setup_component(hass, "otbr", {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "otbr/info",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_get_info_fetch_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test async_get_info."""
    await async_setup_component(hass, "otbr", {})

    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/info",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "get_dataset_failed"


async def test_create_network(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test create network."""

    with patch(
        "python_otbr_api.OTBR.create_active_dataset"
    ) as create_dataset_mock, patch(
        "python_otbr_api.OTBR.set_enabled"
    ) as set_enabled_mock, patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16
    ) as get_active_dataset_tlvs_mock, patch(
        "homeassistant.components.thread.dataset_store.DatasetStore.async_add"
    ) as mock_add:
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/create_network",
            }
        )

        msg = await websocket_client.receive_json()
        assert msg["id"] == 5
        assert msg["success"]
        assert msg["result"] is None

    create_dataset_mock.assert_called_once_with(
        python_otbr_api.models.OperationalDataSet(
            channel=15, network_name="home-assistant"
        )
    )
    assert len(set_enabled_mock.mock_calls) == 2
    assert set_enabled_mock.mock_calls[0][1][0] is False
    assert set_enabled_mock.mock_calls[1][1][0] is True
    get_active_dataset_tlvs_mock.assert_called_once()
    mock_add.assert_called_once_with("Open Thread Border Router", DATASET_CH16.hex())


async def test_create_network_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test create network."""
    await async_setup_component(hass, "otbr", {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "otbr/create_network",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_create_network_fails_1(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test create network."""
    await async_setup_component(hass, "otbr", {})

    with patch(
        "python_otbr_api.OTBR.set_enabled",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/create_network",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "set_enabled_failed"


async def test_create_network_fails_2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test create network."""
    await async_setup_component(hass, "otbr", {})

    with patch(
        "python_otbr_api.OTBR.set_enabled",
    ), patch(
        "python_otbr_api.OTBR.create_active_dataset",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/create_network",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "create_active_dataset_failed"


async def test_create_network_fails_3(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test create network."""
    await async_setup_component(hass, "otbr", {})

    with patch(
        "python_otbr_api.OTBR.set_enabled",
        side_effect=[None, python_otbr_api.OTBRError],
    ), patch(
        "python_otbr_api.OTBR.create_active_dataset",
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/create_network",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "set_enabled_failed"


async def test_create_network_fails_4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test create network."""
    await async_setup_component(hass, "otbr", {})

    with patch("python_otbr_api.OTBR.set_enabled"), patch(
        "python_otbr_api.OTBR.create_active_dataset"
    ), patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/create_network",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "get_active_dataset_tlvs_failed"


async def test_create_network_fails_5(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test create network."""
    await async_setup_component(hass, "otbr", {})

    with patch("python_otbr_api.OTBR.set_enabled"), patch(
        "python_otbr_api.OTBR.create_active_dataset"
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/create_network",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "get_active_dataset_tlvs_empty"


async def test_get_extended_address(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test get extended address."""

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        return_value=bytes.fromhex("4EF6C4F3FF750626"),
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/get_extended_address",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == {"extended_address": "4EF6C4F3FF750626".lower()}


async def test_get_extended_address_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get extended address."""
    await async_setup_component(hass, "otbr", {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "otbr/get_extended_address",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_get_extended_address_fetch_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test get extended address."""
    await async_setup_component(hass, "otbr", {})

    with patch(
        "python_otbr_api.OTBR.get_extended_address",
        side_effect=python_otbr_api.OTBRError,
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/get_extended_address",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "get_extended_address_failed"
