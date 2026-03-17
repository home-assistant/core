"""Test websocket API."""

from collections.abc import Generator
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.models import User
from homeassistant.components.hassio import HASSIO_USER_NAME
from homeassistant.components.hassio.const import DATA_CONFIG_STORE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockUser
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(
    aioclient_mock: AiohttpClientMocker,
    supervisor_is_connected: AsyncMock,
    resolution_info: AsyncMock,
    addon_info: AsyncMock,
    host_info: AsyncMock,
    supervisor_root_info: AsyncMock,
    homeassistant_info: AsyncMock,
    supervisor_info: AsyncMock,
    addons_list: AsyncMock,
    network_info: AsyncMock,
    os_info: AsyncMock,
) -> None:
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    supervisor_root_info.return_value = replace(
        supervisor_root_info.return_value, hassos=None
    )
    addons_list.return_value.pop(1)
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )


@pytest.fixture
def mock_hassio_user_id() -> Generator[None]:
    """Mock the HASSIO user ID for snapshot testing."""
    original_user_init = User.__init__

    def mock_user_init(self, *args, **kwargs):
        with patch("homeassistant.auth.models.uuid.uuid4") as mock_uuid:
            if kwargs.get("name") == HASSIO_USER_NAME:
                mock_uuid.return_value = UUID(bytes=b"very_very_random", version=4)
            else:
                mock_uuid.return_value = uuid4()
            original_user_init(self, *args, **kwargs)

    with patch.object(User, "__init__", mock_user_init):
        yield


@pytest.mark.usefixtures("hassio_env", "mock_hassio_user_id")
@pytest.mark.parametrize(
    "storage_data",
    [
        {},
        {
            "hassio": {
                "data": {
                    "hassio_user": "00112233445566778899aabbccddeeff",
                    "update_config": {
                        "add_on_backup_before_update": False,
                        "add_on_backup_retain_copies": 1,
                        "core_backup_before_update": False,
                    },
                },
                "key": "hassio",
                "minor_version": 1,
                "version": 1,
            }
        },
        {
            "hassio": {
                "data": {
                    "hassio_user": "00112233445566778899aabbccddeeff",
                    "update_config": {
                        "add_on_backup_before_update": True,
                        "add_on_backup_retain_copies": 2,
                        "core_backup_before_update": True,
                    },
                },
                "key": "hassio",
                "minor_version": 1,
                "version": 1,
            }
        },
    ],
)
async def test_load_config_store(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    hass_storage: dict[str, Any],
    storage_data: dict[str, dict[str, Any]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test loading the config store."""
    hass_storage.update(storage_data)

    user = MockUser(id="00112233445566778899aabbccddeeff", system_generated=True)
    user.add_to_hass(hass)
    await hass.auth.async_create_refresh_token(user)
    await hass.auth.async_update_user(user, group_ids=[GROUP_ID_ADMIN])

    with patch("homeassistant.components.hassio.config.STORE_DELAY_SAVE", 0):
        assert await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert hass.data[DATA_CONFIG_STORE].data.to_dict() == snapshot


@pytest.mark.usefixtures("hassio_env", "mock_hassio_user_id")
async def test_save_config_store(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    hass_storage: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test saving the config store."""
    with patch("homeassistant.components.hassio.config.STORE_DELAY_SAVE", 0):
        assert await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert hass_storage[DOMAIN] == snapshot
