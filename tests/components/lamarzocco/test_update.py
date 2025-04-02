"""Tests for the La Marzocco Update Entities."""

from unittest.mock import MagicMock, patch

from pylamarzocco.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_update(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco updates."""
    with patch("homeassistant.components.lamarzocco.PLATFORMS", [Platform.UPDATE]):
        await async_init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_entites(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco update entities."""

    serial_number = mock_lamarzocco.serial_number

    await async_init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: f"update.{serial_number}_gateway_firmware",
        },
        blocking=True,
    )

    mock_lamarzocco.update_firmware.assert_called_once_with()


async def test_update_error(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error during update."""

    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get(f"update.{mock_lamarzocco.serial_number}_gateway_firmware")
    assert state

    mock_lamarzocco.update_firmware.side_effect = RequestNotSuccessful("Boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: f"update.{mock_lamarzocco.serial_number}_gateway_firmware",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "update_failed"
