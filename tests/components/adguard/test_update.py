"""Tests for the AdGuard Home update entity."""

from unittest.mock import AsyncMock, patch

from adguardhome import AdGuardHomeError
from adguardhome.update import AdGuardHomeAvailableUpdate
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update platform."""
    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_disabled(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update is disabled."""
    mock_adguard.update.update_available.return_value = AdGuardHomeAvailableUpdate(
        disabled=True,
    )

    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    assert not hass.states.async_all()


async def test_update_install(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update installation."""
    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.adguard_home"},
        blocking=True,
    )
    mock_adguard.update.begin_update.assert_called_once()


async def test_update_install_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update install failed."""
    mock_adguard.update.begin_update.side_effect = AdGuardHomeError("boom")

    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry, mock_adguard)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.adguard_home"},
            blocking=True,
        )
