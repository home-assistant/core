"""Tests for the Portainer switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    ("entity_id", "turn_on_method", "turn_off_method", "expected_args"),
    [
        (
            "switch.practical_morse_container",
            "start_container",
            "stop_container",
            (1, "ee20facfb3b3ed4cd362c1e88fc89a53908ad05fb3a4103bca3f9b28292d14bf"),
        ),
        (
            "switch.webstack_stack",
            "start_stack",
            "stop_stack",
            (1, 1),
        ),
    ],
)
@pytest.mark.parametrize("service_call", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_turn_off_on(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    turn_on_method: str,
    turn_off_method: str,
    expected_args: tuple,
    service_call: str,
) -> None:
    """Test the switches. Have you tried to turn it off and on again?"""
    await setup_integration(hass, mock_config_entry)

    client_method = (
        turn_on_method if service_call == SERVICE_TURN_ON else turn_off_method
    )
    method_mock = getattr(mock_portainer_client, client_method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service_call,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    method_mock.assert_called_once_with(*expected_args)


@pytest.mark.parametrize(
    ("entity_id", "turn_on_method", "turn_off_method"),
    [
        (
            "switch.practical_morse_container",
            "start_container",
            "stop_container",
        ),
        (
            "switch.webstack_stack",
            "start_stack",
            "stop_stack",
        ),
    ],
)
@pytest.mark.parametrize("service_call", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.parametrize(
    ("raise_exception", "expected_exception"),
    [
        (PortainerAuthenticationError, HomeAssistantError),
        (PortainerConnectionError, HomeAssistantError),
        (PortainerTimeoutError, HomeAssistantError),
    ],
)
async def test_turn_off_on_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    turn_on_method: str,
    turn_off_method: str,
    service_call: str,
    raise_exception: Exception,
    expected_exception: Exception,
) -> None:
    """Test the switches. Have you tried to turn it off and on again? This time they will do boom!"""
    await setup_integration(hass, mock_config_entry)

    client_method = (
        turn_on_method if service_call == SERVICE_TURN_ON else turn_off_method
    )
    method_mock = getattr(mock_portainer_client, client_method)

    method_mock.side_effect = raise_exception
    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service_call,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
