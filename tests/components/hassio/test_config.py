"""Test websocket API."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from syrupy import SnapshotAssertion

from homeassistant.auth.const import GROUP_ID_ADMIN
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
) -> None:
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {"supervisor": "222", "homeassistant": "0.110.0", "hassos": None},
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "data": {
                    "chassis": "vm",
                    "operating_system": "Debian GNU/Linux 10 (buster)",
                    "kernel": "4.19.0-6-amd64",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "auto_update": True,
                "addons": [
                    {
                        "name": "test",
                        "state": "started",
                        "slug": "test",
                        "installed": True,
                        "update_available": True,
                        "icon": False,
                        "version": "2.0.0",
                        "version_latest": "2.0.1",
                        "repository": "core",
                        "url": "https://github.com/home-assistant/addons/test",
                    },
                ],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )
    aioclient_mock.get(
        "http://127.0.0.1/network/info",
        json={
            "result": "ok",
            "data": {
                "host_internet": True,
                "supervisor_internet": True,
            },
        },
    )


@pytest.mark.usefixtures("hassio_env")
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

    with (
        patch("homeassistant.components.hassio.config.STORE_DELAY_SAVE", 0),
        patch("uuid.uuid4", return_value=UUID(bytes=b"very_very_random", version=4)),
    ):
        assert await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert hass.data[DATA_CONFIG_STORE].data.to_dict() == snapshot


@pytest.mark.usefixtures("hassio_env")
async def test_save_config_store(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    supervisor_client: AsyncMock,
    hass_storage: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test saving the config store."""
    with (
        patch("homeassistant.components.hassio.config.STORE_DELAY_SAVE", 0),
        patch("uuid.uuid4", return_value=UUID(bytes=b"very_very_random", version=4)),
    ):
        assert await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert hass_storage[DOMAIN] == snapshot
