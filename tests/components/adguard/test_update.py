"""Tests for the AdGuard Home update entity."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, call, patch

from adguardhome import AdGuardHomeError, AvailableUpdate
from awesomeversion import AwesomeVersion
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.components.update import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.UPDATE]


@pytest.mark.usefixtures("init_integration")
async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_disabled(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update is disabled."""
    mock_adguard.update.get.return_value = AvailableUpdate(
        disabled=True,
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert not hass.states.async_all()


async def test_update_no_new_version(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the update entity without a new version of AdGuard Home."""
    mock_adguard.update.get.return_value = AvailableUpdate(disabled=False)

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("update.adguard_home")
    assert state
    assert state.attributes[ATTR_LATEST_VERSION] is None


async def test_update_check_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup after a failed update check and version refresh without switches."""
    mock_adguard.update.get.side_effect = AdGuardHomeError("No internet")

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("update.adguard_home")
    assert state
    assert state.state == STATE_UNAVAILABLE
    mock_adguard.status.assert_awaited_once()

    mock_adguard.reset_mock()
    mock_adguard.update.get.side_effect = None
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, version=AwesomeVersion("v0.107.51")
    )
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_adguard.mock_calls == []

    freezer.tick(timedelta(seconds=290))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_adguard.mock_calls == [call.status(), call.update.get()]
    assert (
        hass.states.get("update.adguard_home").attributes[ATTR_INSTALLED_VERSION]
        == "v0.107.51"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device.sw_version == "v0.107.51"


@pytest.mark.usefixtures("init_integration")
async def test_update_install(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
) -> None:
    """Test the adguard update installation."""
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.adguard_home"},
        blocking=True,
    )

    mock_adguard.update.install.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_update_install_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
) -> None:
    """Test the adguard update install failed."""
    mock_adguard.update.install.side_effect = AdGuardHomeError("boom")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.adguard_home"},
            blocking=True,
        )
