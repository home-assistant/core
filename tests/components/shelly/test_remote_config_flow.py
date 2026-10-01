"""Test the native Shelly remote setup and credential management flows."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

from aioshelly.exceptions import InvalidAuthError
import pytest
from yarl import URL

from homeassistant.components.shelly.const import (
    CONF_CONNECTION_TYPE,
    CONF_REMOTE_CREDENTIAL,
    CONNECTION_REMOTE_WS,
    DOMAIN,
)
from homeassistant.components.shelly.remote_connection import RemoteConnectionManager
from homeassistant.const import CONF_EXTERNAL_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.translation import async_get_translations

from .test_remote import DEVICE_INFO

from tests.common import MockConfigEntry


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
    """A challenge prompts for device credentials and reuses the same socket."""
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
        await finish(hass, result["flow_id"])
        await hass.async_block_till_done()
    assert (manager.lookup(URL(old_url).query["remote_key"]) is None) is confirm
    assert (manager.lookup(URL(url).query["remote_key"]) is not None) is confirm
    assert entry.data[CONF_REMOTE_CREDENTIAL] == (
        new_record.digest if confirm else old_record.digest
    )
    assert URL(url).query["remote_key"] not in repr(entry.as_dict())
