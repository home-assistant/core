"""Test for Roborock init."""

import pathlib
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from roborock import (
    RoborockInvalidCredentials,
    RoborockInvalidUserAgreement,
    RoborockNoUserAgreement,
)
from roborock.exceptions import RoborockException

from homeassistant.components.roborock.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.setup import async_setup_component

from .conftest import FakeDevice
from .mock_data import ROBOROCK_RRUID, USER_EMAIL

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_unload_entry(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    device_manager: AsyncMock,
) -> None:
    """Test unloading roborock integration."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert setup_entry.state is ConfigEntryState.LOADED

    assert device_manager.get_devices.called
    assert not device_manager.close.called

    # Unload the config entry and verify that the device manager is closed
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.NOT_LOADED

    assert device_manager.close.called


async def test_home_assistant_stop(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    device_manager: AsyncMock,
) -> None:
    """Test shutting down Home Assistant."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert setup_entry.state is ConfigEntryState.LOADED

    assert not device_manager.close.called

    # Perform Home Assistant stop and verify that device manager is closed
    await hass.async_stop()

    assert device_manager.close.called


async def test_reauth_started(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test reauth flow started."""
    with patch(
        "homeassistant.components.roborock.create_device_manager",
        side_effect=RoborockInvalidCredentials(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]])
@pytest.mark.parametrize(
    ("exists", "is_dir", "rmtree_called"),
    [
        (True, True, True),
        (False, False, False),
        (True, False, False),
    ],
    ids=[
        "old_storage_removed",
        "new_storage_ignored",
        "no_existing_storage",
    ],
)
async def test_remove_old_storage_directory(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    storage_path: pathlib.Path,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    exists: bool,
    is_dir: bool,
    rmtree_called: bool,
) -> None:
    """Test cleanup of old old map storage."""
    with (
        patch(
            "homeassistant.components.roborock.roborock_storage.Path.exists",
            return_value=exists,
        ),
        patch(
            "homeassistant.components.roborock.roborock_storage.Path.is_dir",
            return_value=is_dir,
        ),
        patch(
            "homeassistant.components.roborock.roborock_storage.shutil.rmtree",
        ) as mock_rmtree,
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_roborock_entry.state is ConfigEntryState.LOADED

    assert mock_rmtree.called == rmtree_called


@pytest.mark.parametrize("platforms", [[Platform.IMAGE]])
async def test_oserror_remove_storage_directory(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    storage_path: pathlib.Path,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we gracefully handle failing to remove old map storage."""
    with (
        patch(
            "homeassistant.components.roborock.roborock_storage.Path.exists",
            return_value=True,
        ),
        patch(
            "homeassistant.components.roborock.roborock_storage.Path.is_dir",
            return_value=True,
        ),
        patch(
            "homeassistant.components.roborock.roborock_storage.shutil.rmtree",
            side_effect=OSError,
        ) as mock_rmtree,
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_roborock_entry.state is ConfigEntryState.LOADED

    assert mock_rmtree.called
    assert "Unable to remove map files" in caplog.text


async def test_not_supported_protocol(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    fake_devices: list[FakeDevice],
) -> None:
    """Test that we output a message on incorrect protocol."""
    fake_devices[0].v1_properties = None
    fake_devices[0].zeo = None
    fake_devices[0].dyad = None
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()
    assert "because its protocol version " in caplog.text


async def test_invalid_user_agreement(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that we fail setting up if the user agreement is out of date."""
    with patch(
        "homeassistant.components.roborock.create_device_manager",
        side_effect=RoborockInvalidUserAgreement(),
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY
        assert (
            mock_roborock_entry.error_reason_translation_key == "invalid_user_agreement"
        )


async def test_no_user_agreement(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that we fail setting up if the user has no agreement."""
    with patch(
        "homeassistant.components.roborock.create_device_manager",
        side_effect=RoborockNoUserAgreement(),
    ):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY
        assert mock_roborock_entry.error_reason_translation_key == "no_user_agreement"


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_stale_device(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test that we remove a device if it no longer is given by home_data."""
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert mock_roborock_entry.state is ConfigEntryState.LOADED
    existing_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert {device.name for device in existing_devices} == {
        "Roborock S7 MaxV",
        "Roborock S7 MaxV Dock",
        "Roborock S7 2",
        "Roborock S7 2 Dock",
        "Dyad Pro",
        "Zeo One",
    }
    fake_devices.pop(0)  # Remove one robot

    await hass.config_entries.async_reload(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()
    new_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert {device.name for device in new_devices} == {
        "Roborock S7 2",
        "Roborock S7 2 Dock",
        "Dyad Pro",
        "Zeo One",
    }


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_no_stale_device(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test that we don't remove a device if fails to setup."""
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert mock_roborock_entry.state is ConfigEntryState.LOADED
    existing_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert {device.name for device in existing_devices} == {
        "Roborock S7 MaxV",
        "Roborock S7 MaxV Dock",
        "Roborock S7 2",
        "Roborock S7 2 Dock",
        "Dyad Pro",
        "Zeo One",
    }

    await hass.config_entries.async_reload(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()
    new_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert {device.name for device in new_devices} == {
        "Roborock S7 MaxV",
        "Roborock S7 MaxV Dock",
        "Roborock S7 2",
        "Roborock S7 2 Dock",
        "Dyad Pro",
        "Zeo One",
    }


async def test_migrate_config_entry_unique_id(
    hass: HomeAssistant,
    config_entry_data: dict[str, Any],
) -> None:
    """Test migrating the config entry unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_EMAIL,
        data=config_entry_data,
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == ROBOROCK_RRUID


async def test_cloud_api_repair(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that a repair is created when we use the cloud api."""

    # Fake that the device is only reachable via cloud
    fake_vacuum.is_connected = True
    fake_vacuum.is_local_connected = False

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1
    # Check that both expected device names are present, regardless of order
    assert all(
        issue.translation_key == "cloud_api_used"
        for issue in issue_registry.issues.values()
    )
    names = {
        issue.translation_placeholders["device_name"]
        for issue in issue_registry.issues.values()
    }
    assert names == {"Roborock S7 MaxV"}
    await hass.config_entries.async_unload(mock_roborock_entry.entry_id)

    # Now fake that the device is reachable locally again
    fake_vacuum.is_local_connected = True

    # Set it back up
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_zeo_device_fails_setup(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    fake_devices: list[FakeDevice],
) -> None:
    """Simulate an error while setting up a zeo device."""
    # We have a single zeo device in the test setup. Find it then set it to fail.
    zeo_device = next(
        (device for device in fake_devices if device.zeo is not None),
        None,
    )
    assert zeo_device is not None
    zeo_device.zeo.query_values.side_effect = RoborockException("Simulated Zeo failure")

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert mock_roborock_entry.state is ConfigEntryState.LOADED

    # The current behavior is that we do not add the Zeo device if it fails to setup
    found_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert {device.name for device in found_devices} == {
        "Roborock S7 MaxV",
        "Roborock S7 MaxV Dock",
        "Roborock S7 2",
        "Roborock S7 2 Dock",
        "Dyad Pro",
        # Zeo device is missing
    }


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_dyad_device_fails_setup(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    fake_devices: list[FakeDevice],
) -> None:
    """Simulate an error while setting up a dyad device."""
    # We have a single dyad device in the test setup. Find it then set it to fail.
    dyad_device = next(
        (device for device in fake_devices if device.dyad is not None),
        None,
    )
    assert dyad_device is not None
    dyad_device.dyad.query_values.side_effect = RoborockException(
        "Simulated Dyad failure"
    )

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    assert mock_roborock_entry.state is ConfigEntryState.LOADED

    # The current behavior is that we do not add the Dyad device if it fails to setup
    found_devices = device_registry.devices.get_devices_for_config_entry_id(
        mock_roborock_entry.entry_id
    )
    assert {device.name for device in found_devices} == {
        "Roborock S7 MaxV",
        "Roborock S7 MaxV Dock",
        "Roborock S7 2",
        "Roborock S7 2 Dock",
        # Dyad device is missing
        "Zeo One",
    }
