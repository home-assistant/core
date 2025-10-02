"""Tests for the Portainer button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

BUTTON_DOMAIN = "button"


async def test_all_button_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Portainer button entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.BUTTON],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("action", "client_method"),
    [
        ("restart", "restart_container"),
    ],
)
async def test_buttons(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    client_method: str,
) -> None:
    """Test pressing a Portainer container action button triggers client call. Click, click!"""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.BUTTON],
    ):
        await setup_integration(hass, mock_config_entry)

    entity_id = f"button.practical_morse_{action}_container"
    method_mock = getattr(mock_portainer_client, client_method)
    pre_calls = len(method_mock.mock_calls)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(method_mock.mock_calls) == pre_calls + 1
