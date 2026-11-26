"""Test the APsystems Lake_6 setup."""

from dataclasses import replace
import datetime as dt
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.apsystems import LAKE6_PLATFORMS
from homeassistant.components.apsystems.const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_EZ1,
    DOMAIN,
)
from homeassistant.components.apsystems.lake6.client import Lake6ApiError
from homeassistant.components.apsystems.lake6.const import LAKE6_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

SCAN_INTERVAL = dt.timedelta(seconds=LAKE6_UPDATE_INTERVAL)


@pytest.mark.usefixtures("mock_lake6")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test the Lake_6 entry loads and unloads."""
    await setup_integration(hass, mock_lake6_config_entry)
    assert mock_lake6_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_lake6_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_lake6_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test an unreachable device puts the entry into a retry."""
    mock_lake6.async_get_device.side_effect = Lake6ApiError("unreachable")

    await setup_integration(hass, mock_lake6_config_entry)

    assert mock_lake6_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_rejects_another_device(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test an address that now answers for another unit is refused."""
    mock_lake6.async_get_device.return_value = replace(
        mock_lake6.async_get_device.return_value, dev_id="OTHER_DEV_ID"
    )

    await setup_integration(hass, mock_lake6_config_entry)

    assert mock_lake6_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("mock_apsystems")
async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test a version 1 entry is backfilled as EZ1."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "127.0.0.1"},
        unique_id="MY_SERIAL_NUMBER",
        version=1,
    )

    await setup_integration(hass, entry)

    # `device_type` only backfills EZ1 data, so the major version stays put.
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_EZ1


@pytest.mark.parametrize("platform", LAKE6_PLATFORMS, ids=lambda platform: platform)
@pytest.mark.usefixtures("mock_lake6", "entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_lake6_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    platform: Platform,
) -> None:
    """Test the entities of one platform."""
    # Snapshotting needs a single platform per test, so narrow the forward list.
    with patch("homeassistant.components.apsystems.LAKE6_PLATFORMS", [platform]):
        await setup_integration(hass, mock_lake6_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_lake6_config_entry.entry_id
        )


async def test_modes_are_throttled(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test /modes is not fetched on every 60 second refresh."""
    await setup_integration(hass, mock_lake6_config_entry)

    assert mock_lake6.async_get_energies.await_count == 1
    assert mock_lake6.async_get_modes.await_count == 1

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_lake6.async_get_energies.await_count == 2
    assert mock_lake6.async_get_modes.await_count == 1
