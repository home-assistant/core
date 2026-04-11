"""Tests for the ntfy update platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiontfy.exceptions import (
    NtfyNotFoundPageError,
    NtfyUnauthorizedAuthenticationError,
)
from aiontfy.update import UpdateCheckerError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ntfy.const import DEFAULT_URL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def update_only() -> Generator[None]:
    """Enable only the update platform."""
    with patch(
        "homeassistant.components.ntfy.PLATFORMS",
        [Platform.UPDATE],
    ):
        yield


@pytest.mark.usefixtures("mock_aiontfy", "mock_update_checker")
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Snapshot test states of update platform."""
    ws_client = await hass_ws_client(hass)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="ntfy.example",
        data={
            CONF_URL: "https://ntfy.example/",
            CONF_USERNAME: None,
            CONF_TOKEN: "token",
            CONF_VERIFY_SSL: True,
        },
        entry_id="123456789",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.ntfy_example_ntfy_version",
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] == "**RELEASE_NOTES**"


@pytest.mark.usefixtures("mock_aiontfy")
async def test_update_checker_error(
    hass: HomeAssistant,
    mock_update_checker: AsyncMock,
) -> None:
    """Test update entity update checker error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="ntfy.example",
        data={
            CONF_URL: "https://ntfy.example/",
            CONF_USERNAME: None,
            CONF_TOKEN: "token",
            CONF_VERIFY_SSL: True,
        },
        entry_id="123456789",
    )
    mock_update_checker.latest_release.side_effect = UpdateCheckerError

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("update.ntfy_example_ntfy_version")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception",
    [
        NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
        NtfyNotFoundPageError(40401, 404, "page not found"),
    ],
    ids=["not an admin", "version < 2.17.0"],
)
@pytest.mark.usefixtures("mock_update_checker")
async def test_version_errors(
    hass: HomeAssistant,
    mock_aiontfy: AsyncMock,
    exception: Exception,
) -> None:
    """Test update entity is not created when version endpoint is not available."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="ntfy.example",
        data={
            CONF_URL: "https://ntfy.example/",
            CONF_USERNAME: None,
            CONF_TOKEN: "token",
            CONF_VERIFY_SSL: True,
        },
        entry_id="123456789",
    )
    mock_aiontfy.version.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("update.ntfy_example_ntfy_version")
    assert state is None


@pytest.mark.usefixtures("mock_aiontfy", "mock_update_checker")
async def test_with_official_server(hass: HomeAssistant) -> None:
    """Test update entity is not created when using official ntfy server."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="ntfy.sh",
        data={
            CONF_URL: DEFAULT_URL,
            CONF_USERNAME: None,
            CONF_TOKEN: "token",
            CONF_VERIFY_SSL: True,
        },
        entry_id="123456789",
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("update.ntfy_sh_ntfy_version")
    assert state is None
