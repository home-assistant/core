"""Tests for KEBA P40 switches."""

from unittest.mock import AsyncMock, patch

from keba_kecontact_p40 import KebaP40Error
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


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the KEBA P40 switches via snapshot."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_charging_switch_calls_client(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the charging switch starts and stops charging."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.garage_charging"},
        blocking=True,
    )
    mock_client.stop_charging.assert_called_once_with("21900042")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.garage_charging"},
        blocking=True,
    )
    mock_client.start_charging.assert_called_once_with("21900042")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_charging_switch_turn_on_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a start_charging error raises HomeAssistantError."""
    mock_client.start_charging.side_effect = KebaP40Error
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.garage_charging"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_charging_switch_turn_off_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a stop_charging error raises HomeAssistantError."""
    mock_client.stop_charging.side_effect = KebaP40Error
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.garage_charging"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_availability_switch_calls_client(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the availability switch calls set_availability."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.garage_available"},
        blocking=True,
    )
    mock_client.set_availability.assert_called_once_with("21900042", False)

    mock_client.set_availability.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.garage_available"},
        blocking=True,
    )
    mock_client.set_availability.assert_called_once_with("21900042", True)
