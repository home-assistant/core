"""Tests for the Portainer switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_portainer_client")
async def test_all_switch_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Portainer switch entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("service_call", "client_method"),
    [
        (SERVICE_TURN_ON, "start_container"),
        (SERVICE_TURN_OFF, "stop_container"),
    ],
)
async def test_turn_off_on(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_call: str,
    client_method: str,
) -> None:
    """Test the switches. Have you tried to turn it off and on again?"""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    entity_id = "switch.practical_morse_container_up_down"
    method_mock = getattr(mock_portainer_client, client_method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service_call,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Matches the endpoint ID and container ID
    method_mock.assert_called_once_with(
        1, "ee20facfb3b3ed4cd362c1e88fc89a53908ad05fb3a4103bca3f9b28292d14bf"
    )
