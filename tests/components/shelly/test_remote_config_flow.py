"""Test the native Shelly remote setup and credential management flows."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from aioshelly.rpc_device import WsServerConnection
import pytest
from yarl import URL

from homeassistant.components.shelly.const import (
    CONF_CONNECTION_TYPE,
    CONF_REMOTE_CREDENTIAL,
    CONNECTION_REMOTE_WS,
    DOMAIN,
)
from homeassistant.components.shelly.remote_connection import (
    RemoteConnectionManager,
    RemoteCredential,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EXTERNAL_URL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.translation import async_get_translations

from .test_remote import DEVICE_INFO, make_socket

from tests.common import MockConfigEntry

type RotationContext = tuple[
    RemoteConnectionManager, MockConfigEntry, str, RemoteCredential, ConfigFlowResult
]


def attach_rotation_socket(
    manager: RemoteConnectionManager, record: RemoteCredential
) -> tuple[WsServerConnection, MagicMock]:
    """Attach an identified candidate socket to the native RPC transport."""
    websocket = make_socket(DEVICE_INFO)

    async def close(*_args: object, **_kwargs: object) -> None:
        websocket.closed = True

    websocket.close.side_effect = close
    record.info = DEVICE_INFO
    record.ready.set()
    record.websockets.add(websocket)
    connection = manager.server.get_or_create_connection(record.device_id)
    connection.attach(DEVICE_INFO["id"], websocket)
    connection.calls = AsyncMock(
        return_value=[
            {"sys": {"device": {"name": "Remote test"}}},
            {"sys": {"wakeup_period": 0}},
        ]
    )
    return connection, websocket


@pytest.fixture
async def rotation_flow(hass: HomeAssistant) -> AsyncGenerator[RotationContext]:
    """Open a replacement form while the original credential owns a live socket."""
    manager = RemoteConnectionManager(hass)
    old_record, old_url = manager.create_credential(URL("https://ha.example.com"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
            CONF_REMOTE_CREDENTIAL: old_record.digest,
            CONF_PASSWORD: "device-password",
        },
    )
    entry.add_to_hass(hass)
    manager.register_entry(entry)
    attach_rotation_socket(manager, old_record)
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_get_remote_manager",
            return_value=manager,
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "remote_regenerate"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EXTERNAL_URL: "https://ha.example.com"}
        )
        token = URL(result["description_placeholders"]["connection_url"]).query[
            "remote_key"
        ]
        yield manager, entry, old_url, manager.lookup(token), result
        for progress in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
            hass.config_entries.flow.async_abort(progress["flow_id"])
        await hass.async_block_till_done()


async def start_remote_flow(
    hass: HomeAssistant, manager: RemoteConnectionManager
) -> dict:
    """Start a user-selected remote flow and generate its connection URL."""
    with patch(
        "homeassistant.components.shelly.config_flow.async_get_remote_manager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "remote"}
        )
        assert result["step_id"] == "remote"
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EXTERNAL_URL: "https://ha.example.com"}
        )


async def test_remote_progress_shows_connection_url(hass: HomeAssistant) -> None:
    """Render the pairing URL using the translation key the frontend reads."""
    manager = RemoteConnectionManager(hass)
    with patch(
        "homeassistant.components.shelly.config_flow.async_get_remote_manager",
        return_value=manager,
    ):
        result = await start_remote_flow(hass, manager)
        translations = await async_get_translations(hass, "en", "config", {DOMAIN})
        description = translations[
            f"component.{DOMAIN}.config.progress.{result['progress_action']}"
        ]
        assert "{connection_url}" in description
        url = result["description_placeholders"]["connection_url"]
        assert f"`{url}`" in description.format(**result["description_placeholders"])
        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()
    assert not manager.credentials


@pytest.mark.usefixtures("mock_setup", "mock_setup_entry")
async def test_remote_pairing_flow_without_host(hass: HomeAssistant) -> None:
    """Wait for a queried identity and create an ordinary hostless config entry."""
    manager = RemoteConnectionManager(hass)
    result = await start_remote_flow(hass, manager)
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    url = result["description_placeholders"]["connection_url"]
    record = manager.lookup(URL(url).query["remote_key"])
    record.device_id = "AABBCCDDEEFF"
    record.info = DEVICE_INFO
    connection = manager.server.get_or_create_connection(record.device_id)
    connection.attach(DEVICE_INFO["id"], MagicMock(closed=False))
    connection.calls = AsyncMock(
        return_value=[
            {"sys": {"device": {"name": "Remote test"}}},
            {"sys": {"wakeup_period": 0}},
        ]
    )
    record.ready.set()
    with patch(
        "homeassistant.components.shelly.config_flow.async_get_remote_manager",
        return_value=manager,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["step_id"] == "remote_confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CONNECTION_TYPE] == CONNECTION_REMOTE_WS
    assert result["data"][CONF_REMOTE_CREDENTIAL] == record.digest
    assert "host" not in result["data"]
    assert URL(url).query["remote_key"] not in repr(result["data"])
    assert connection.connected


@pytest.mark.usefixtures("mock_setup", "mock_setup_entry")
@pytest.mark.parametrize(
    ("expires_in", "rpc_calls"),
    [
        pytest.param(0, 0, id="expired-before-confirmation"),
        pytest.param(600, 1, id="expired-during-rpc"),
    ],
)
async def test_expired_remote_pairing_confirmation(
    hass: HomeAssistant, expires_in: int, rpc_calls: int
) -> None:
    """An expired pairing cannot become a permanent credential on confirmation."""
    manager = RemoteConnectionManager(hass)
    result = await start_remote_flow(hass, manager)
    record = next(iter(manager.credentials.values()))
    record.device_id = "AABBCCDDEEFF"
    record.info = DEVICE_INFO
    connection = manager.server.get_or_create_connection(record.device_id)
    connection.attach(DEVICE_INFO["id"], MagicMock(closed=False))

    async def expire_during_rpc(*_args: object) -> list[dict]:
        record.expires_at = 0
        return [
            {"sys": {"device": {"name": "Remote test"}}},
            {"sys": {"wakeup_period": 0}},
        ]

    connection.calls = AsyncMock(side_effect=expire_during_rpc)
    record.ready.set()
    with patch(
        "homeassistant.components.shelly.config_flow.async_get_remote_manager",
        return_value=manager,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        record.expires_at = asyncio.get_running_loop().time() + expires_in
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "remote_pairing_expired"
    assert connection.calls.await_count == rpc_calls
    assert not manager.credentials
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_remote_invalid_external_url(hass: HomeAssistant) -> None:
    """An insecure external URL cannot generate a pairing credential."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "remote"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EXTERNAL_URL: "http://ha.example.com"}
    )
    assert result["errors"] == {"base": "invalid_external_url"}


async def test_cancelled_pairing_is_revoked(hass: HomeAssistant) -> None:
    """Cancelling a waiting flow removes its temporary verifier."""
    manager = RemoteConnectionManager(hass)
    result = await start_remote_flow(hass, manager)
    token = URL(result["description_placeholders"]["connection_url"]).query[
        "remote_key"
    ]
    with patch(
        "homeassistant.components.shelly.config_flow.async_get_remote_manager",
        return_value=manager,
    ):
        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()
    assert manager.lookup(token) is None


@pytest.mark.usefixtures("mock_setup", "mock_setup_entry")
async def test_remote_device_digest_credentials(hass: HomeAssistant) -> None:
    """A challenge prompts for credentials and a rejected password shows an error."""
    manager = RemoteConnectionManager(hass)
    result = await start_remote_flow(hass, manager)
    record = next(iter(manager.credentials.values()))
    record.device_id = "AABBCCDDEEFF"
    record.info = {**DEVICE_INFO, "auth_en": True}
    connection = manager.server.get_or_create_connection(record.device_id)
    connection.attach(DEVICE_INFO["id"], MagicMock(closed=False))
    connection.calls = AsyncMock(
        side_effect=[
            InvalidAuthError("challenge"),
            InvalidAuthError("invalid credentials"),
            [
                {"sys": {"device": {"name": "Remote auth"}}},
                {"sys": {"wakeup_period": 0}},
            ],
        ]
    )
    record.ready.set()
    with patch(
        "homeassistant.components.shelly.config_flow.async_get_remote_manager",
        return_value=manager,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["step_id"] == "remote_credentials"
        assert not result["errors"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "wrong-password"}
        )
        assert result["step_id"] == "remote_credentials"
        assert result["errors"] == {"base": "invalid_auth"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "device-password"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == "admin"
    assert connection.connected


async def test_revoke_remote_access_flow(hass: HomeAssistant) -> None:
    """Revoke the verifier while retaining the native config entry."""
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Remote",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
            CONF_REMOTE_CREDENTIAL: record.digest,
        },
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_get_remote_manager",
            return_value=manager,
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "remote_revoke"}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_REMOTE_CREDENTIAL] is None
    assert manager.lookup(URL(url).query["remote_key"]) is None


async def confirm_rotation(hass: HomeAssistant, flow_id: str) -> None:
    """Confirm a replacement credential."""
    await hass.config_entries.flow.async_configure(flow_id, {})


async def cancel_rotation(hass: HomeAssistant, flow_id: str) -> None:
    """Cancel a replacement credential."""
    hass.config_entries.flow.async_abort(flow_id)


async def test_expired_remote_regeneration(hass: HomeAssistant) -> None:
    """An old rotation form cannot revive its expired URL or revoke active access."""
    manager = RemoteConnectionManager(hass)
    old_record, old_url = manager.create_credential(URL("https://ha.example.com"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
            CONF_REMOTE_CREDENTIAL: old_record.digest,
        },
    )
    entry.add_to_hass(hass)
    manager.register_entry(entry)
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_get_remote_manager",
            return_value=manager,
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "remote_regenerate"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EXTERNAL_URL: "https://ha.example.com"}
        )
        token = URL(result["description_placeholders"]["connection_url"]).query[
            "remote_key"
        ]
        new_record = manager.lookup(token)
        new_record.expires_at = 0
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "remote_pairing_expired"
    assert entry.data[CONF_REMOTE_CREDENTIAL] == old_record.digest
    assert manager.lookup(URL(old_url).query["remote_key"]) is old_record
    assert manager.lookup(token) is None
    reload.assert_not_awaited()


@pytest.mark.parametrize(
    ("info", "attached_socket", "closed"),
    [
        pytest.param(None, 0, False, id="only-original-socket-connected"),
        pytest.param(DEVICE_INFO, 0, False, id="original-replaced-candidate"),
        pytest.param(None, 1, False, id="identity-not-verified"),
        pytest.param(DEVICE_INFO, 1, True, id="candidate-disconnected"),
    ],
)
async def test_regeneration_requires_candidate_socket(
    hass: HomeAssistant,
    rotation_flow: RotationContext,
    info: dict | None,
    attached_socket: int,
    closed: bool,
) -> None:
    """An old live connection or an unverified candidate cannot confirm rotation."""
    manager, entry, old_url, record, result = rotation_flow
    old_digest = entry.data[CONF_REMOTE_CREDENTIAL]
    connection = manager.server.get_connection(entry.unique_id)
    old_socket = next(iter(manager.credentials[old_digest].websockets))
    candidate = make_socket(DEVICE_INFO)
    candidate.closed = closed
    record.info = info
    record.websockets.add(candidate)
    connection.attach(DEVICE_INFO["id"], (old_socket, candidate)[attached_socket])
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_REMOTE_CREDENTIAL] == old_digest
    assert manager.lookup(URL(old_url).query["remote_key"]) is not None
    assert record.expires_at is not None
    connection.calls.assert_not_awaited()
    old_socket.close.assert_not_awaited()


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        pytest.param(
            InvalidAuthError("invalid credentials"), "invalid_auth", id="auth"
        ),
        pytest.param(
            DeviceConnectionError("disconnected"), "cannot_connect", id="socket"
        ),
        pytest.param(RpcCallError(-1, "RPC failed"), "cannot_connect", id="rpc"),
    ],
)
async def test_regeneration_rpc_failure_preserves_original(
    hass: HomeAssistant,
    rotation_flow: RotationContext,
    failure: Exception,
    error: str,
) -> None:
    """Failed authentication or RPC leaves the original credential valid."""
    manager, entry, old_url, record, result = rotation_flow
    old_digest = entry.data[CONF_REMOTE_CREDENTIAL]
    connection, _ = attach_rotation_socket(manager, record)
    connection.calls.side_effect = failure
    with patch.object(connection, "set_auth_data") as set_auth:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data[CONF_REMOTE_CREDENTIAL] == old_digest
    assert manager.lookup(URL(old_url).query["remote_key"]) is not None
    assert record.expires_at is not None
    set_auth.assert_called_once_with(DEVICE_INFO["id"], "admin", "device-password")


async def expire_candidate(
    _manager: RemoteConnectionManager, record: RemoteCredential
) -> None:
    """Expire admission while its RPC proof is in flight."""
    record.expires_at = 0


async def revoke_candidate(
    manager: RemoteConnectionManager, record: RemoteCredential
) -> None:
    """Revoke admission while its RPC proof is in flight."""
    await manager.revoke(record.digest)


@pytest.mark.parametrize("invalidate", [expire_candidate, revoke_candidate])
async def test_regeneration_invalidated_during_rpc(
    hass: HomeAssistant,
    rotation_flow: RotationContext,
    invalidate: Callable[[RemoteConnectionManager, RemoteCredential], Awaitable[None]],
) -> None:
    """Successful RPC cannot revive a credential expired or revoked while awaiting it."""
    manager, entry, old_url, record, result = rotation_flow
    old_digest = entry.data[CONF_REMOTE_CREDENTIAL]
    connection, _ = attach_rotation_socket(manager, record)
    reply = connection.calls.return_value

    async def invalidate_during_rpc(*_args: object) -> list[dict]:
        await invalidate(manager, record)
        return reply

    connection.calls.side_effect = invalidate_during_rpc
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "remote_pairing_expired"
    assert entry.data[CONF_REMOTE_CREDENTIAL] == old_digest
    assert manager.lookup(URL(old_url).query["remote_key"]) is not None
    assert record.digest not in manager.credentials


async def test_regeneration_socket_replaced_during_rpc(
    hass: HomeAssistant, rotation_flow: RotationContext
) -> None:
    """A reply from the candidate cannot approve a different active socket."""
    manager, entry, old_url, record, result = rotation_flow
    old_digest = entry.data[CONF_REMOTE_CREDENTIAL]
    connection, _ = attach_rotation_socket(manager, record)
    reply = connection.calls.return_value
    replacement = make_socket(DEVICE_INFO)
    record.websockets.add(replacement)

    async def replace_during_rpc(*_args: object) -> list[dict]:
        connection.attach(DEVICE_INFO["id"], replacement)
        return reply

    connection.calls.side_effect = replace_during_rpc
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_REMOTE_CREDENTIAL] == old_digest
    assert manager.lookup(URL(old_url).query["remote_key"]) is not None
    assert record.expires_at is not None


async def test_regeneration_entry_changed_during_rpc(
    hass: HomeAssistant, rotation_flow: RotationContext
) -> None:
    """A stale rotation cannot overwrite a concurrently committed entry credential."""
    manager, entry, old_url, record, result = rotation_flow
    connection, _ = attach_rotation_socket(manager, record)
    reply = connection.calls.return_value
    concurrent, _ = manager.create_credential(URL("https://ha.example.com"))

    async def update_during_rpc(*_args: object) -> list[dict]:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REMOTE_CREDENTIAL: concurrent.digest}
        )
        return reply

    connection.calls.side_effect = update_during_rpc
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "remote_pairing_expired"
    assert entry.data[CONF_REMOTE_CREDENTIAL] == concurrent.digest
    assert manager.lookup(URL(old_url).query["remote_key"]) is not None
    assert record.digest not in manager.credentials


@pytest.mark.parametrize(
    ("finish", "confirm"), [(confirm_rotation, True), (cancel_rotation, False)]
)
async def test_regenerate_remote_credential(
    hass: HomeAssistant,
    finish: Callable[[HomeAssistant, str], Awaitable[None]],
    confirm: bool,
) -> None:
    """Commit rotation revokes only the old credential; cancellation revokes only the new."""
    manager = RemoteConnectionManager(hass)
    old_record, old_url = manager.create_credential(URL("https://ha.example.com"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
            CONF_REMOTE_CREDENTIAL: old_record.digest,
        },
    )
    entry.add_to_hass(hass)
    manager.register_entry(entry)
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_get_remote_manager",
            return_value=manager,
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "remote_regenerate"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EXTERNAL_URL: "https://ha.example.com"}
        )
        url = result["description_placeholders"]["connection_url"]
        new_record = manager.lookup(URL(url).query["remote_key"])
        assert new_record.device_id == entry.unique_id
        assert new_record.entry_id == entry.entry_id
        attach_rotation_socket(manager, new_record)
        await finish(hass, result["flow_id"])
        await hass.async_block_till_done()
    assert (manager.lookup(URL(old_url).query["remote_key"]) is None) is confirm
    assert (manager.lookup(URL(url).query["remote_key"]) is not None) is confirm
    assert entry.data[CONF_REMOTE_CREDENTIAL] == (
        new_record.digest if confirm else old_record.digest
    )
    assert URL(url).query["remote_key"] not in repr(entry.as_dict())
