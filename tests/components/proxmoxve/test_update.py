"""Tests for the Proxmox VE update platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator

ENTITY_ID = "update.pve1_update"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_update_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Proxmox VE update entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


async def test_update_install(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful Proxmox VE node update installation."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    # Dedicated mocks for the ssh connection
    mock_result = MagicMock()
    mock_result.exit_status = 0
    mock_conn = MagicMock()
    mock_conn.run = AsyncMock(return_value=mock_result)
    mock_connect_cm = MagicMock()
    mock_connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_connect_cm.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "homeassistant.components.proxmoxve.update.asyncssh.connect",
        return_value=mock_connect_cm,
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )


async def test_update_release_notes(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that release notes return the expected pending update message."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {"id": 1, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    result = await ws_client.receive_json()
    assert "2 update(s)" in result["result"]


async def test_update_install_failed(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a non-zero exit status raises HomeAssistantError."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    mock_result = MagicMock()
    mock_result.exit_status = 1
    mock_conn = MagicMock()
    mock_conn.run = AsyncMock(return_value=mock_result)
    mock_connect_cm = MagicMock()
    mock_connect_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_connect_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.proxmoxve.update.asyncssh.connect",
            return_value=mock_connect_cm,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (asyncssh.DisconnectError(0, "Connection lost"), "cannot_connect_no_details"),
        (TimeoutError(), "timeout_connect_no_details"),
    ],
)
async def test_update_install_errors(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test node update install error handling."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    mock_connect_cm = MagicMock()
    mock_connect_cm.__aenter__ = AsyncMock(side_effect=exception)
    mock_connect_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.proxmoxve.update.asyncssh.connect",
            return_value=mock_connect_cm,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )
