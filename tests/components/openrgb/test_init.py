"""Tests for the OpenRGB integration init."""

import socket
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from openrgb.utils import ControllerParsingError, OpenRGBDisconnected, SDKVersionError
import pytest

from homeassistant.components.openrgb import async_remove_config_entry_device
from homeassistant.components.openrgb.const import DOMAIN, SCAN_INTERVAL, UID_SEPARATOR
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_entry_setup_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> None:
    """Test entry setup and unload."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_openrgb_client.disconnect.called


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_remove_config_entry_device_server(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that server device cannot be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    server_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )

    assert server_device is not None

    # Try to remove server device - should be blocked
    result = await async_remove_config_entry_device(
        hass, mock_config_entry, server_device
    )

    assert result is False


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_remove_config_entry_device_still_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that connected devices cannot be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

    # Get a device that's in coordinator.data (still connected)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    rgb_device = next(
        (d for d in devices if d.identifiers != {(DOMAIN, mock_config_entry.entry_id)}),
        None,
    )

    # pylint: disable-next=home-assistant-test-non-deterministic
    if rgb_device:
        # Try to remove device that's still connected - should be blocked
        result = await async_remove_config_entry_device(
            hass, mock_config_entry, rgb_device
        )
        assert result is False


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_remove_config_entry_device_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that disconnected devices can be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a device that's not in coordinator.data (disconnected)
    entry_id = mock_config_entry.entry_id
    disconnected_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={
            (
                DOMAIN,
                UID_SEPARATOR.join(
                    [
                        entry_id,
                        "KEYBOARD",
                        "Old Vendor",
                        "Old Device",
                        "OLD123",
                        "Old Location",
                    ]
                ),
            )
        },
        name="Old Disconnected Device",
        via_device=(DOMAIN, entry_id),
    )

    # Try to remove disconnected device - should succeed
    result = await async_remove_config_entry_device(
        hass, mock_config_entry, disconnected_device
    )

    assert result is True


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_remove_config_entry_device_with_multiple_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device removal with multiple domain identifiers."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_id = mock_config_entry.entry_id

    # Create a device with identifiers from multiple domains
    device_with_multiple_identifiers = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={
            ("other_domain", "some_other_id"),  # This should be skipped
            (
                DOMAIN,
                UID_SEPARATOR.join(
                    [
                        entry_id,
                        "DEVICE",
                        "Vendor",
                        "Name",
                        "SERIAL123",
                        "Location",
                    ]
                ),
            ),  # This is a disconnected OpenRGB device
        },
        name="Multi-Domain Device",
        via_device=(DOMAIN, entry_id),
    )

    # Try to remove device - should succeed because the OpenRGB
    # identifier is disconnected
    result = await async_remove_config_entry_device(
        hass, mock_config_entry, device_with_multiple_identifiers
    )

    assert result is True


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ConnectionRefusedError, ConfigEntryState.SETUP_RETRY),
        (OpenRGBDisconnected, ConfigEntryState.SETUP_RETRY),
        (ControllerParsingError, ConfigEntryState.SETUP_RETRY),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (socket.gaierror, ConfigEntryState.SETUP_RETRY),
        (SDKVersionError, ConfigEntryState.SETUP_RETRY),
        (RuntimeError("Test error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry with various exceptions."""
    mock_config_entry.add_to_hass(hass)

    mock_openrgb_client.client_class_mock.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_reconnection_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that coordinator reconnects when update fails."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Reset mock call counts after initial setup
    mock_openrgb_client.update.reset_mock()
    mock_openrgb_client.connect.reset_mock()

    # Simulate the first update call failing, then second succeeding
    mock_openrgb_client.update.side_effect = [
        OpenRGBDisconnected(),
        None,  # Second call succeeds after reconnect
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that disconnect and connect were called (reconnection happened)
    mock_openrgb_client.disconnect.assert_called_once()
    mock_openrgb_client.connect.assert_called_once()

    # Verify that update was called twice (once failed, once after reconnect)
    assert mock_openrgb_client.update.call_count == 2

    # Verify that the light is still available after successful reconnect
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON


async def test_reconnection_fails_second_attempt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that coordinator fails when reconnection also fails."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Reset mock call counts after initial setup
    mock_openrgb_client.update.reset_mock()
    mock_openrgb_client.connect.reset_mock()

    # Simulate the first update call failing, and reconnection also failing
    mock_openrgb_client.update.side_effect = [
        OpenRGBDisconnected(),
        None,  # Second call would succeed if reconnect worked
    ]

    # Simulate connect raising an exception to mimic failed reconnection
    mock_openrgb_client.connect.side_effect = ConnectionRefusedError()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that the light became unavailable after failed reconnection
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Verify that disconnect and connect were called (reconnection was attempted)
    mock_openrgb_client.disconnect.assert_called_once()
    mock_openrgb_client.connect.assert_called_once()

    # Verify that update was only called in the first attempt
    mock_openrgb_client.update.assert_called_once()


async def test_normal_update_without_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that normal updates work without triggering reconnection."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Reset mock call counts after initial setup
    mock_openrgb_client.update.reset_mock()
    mock_openrgb_client.connect.reset_mock()

    # Simulate successful update
    mock_openrgb_client.update.side_effect = None
    mock_openrgb_client.update.return_value = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that disconnect and connect were NOT called (no reconnection needed)
    mock_openrgb_client.disconnect.assert_not_called()
    mock_openrgb_client.connect.assert_not_called()

    # Verify that update was called only once
    mock_openrgb_client.update.assert_called_once()

    # Verify that the light is still available
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("serial", "location", "expected_suffix", "reconnect_location"),
    [
        pytest.param(
            "", "HID: DevSrvsID:111", "hid_0", "HID: DevSrvsID:222", id="hid_no_serial"
        ),
        pytest.param(
            "ABC123",
            "HID: DevSrvsID:111",
            "hid_0",
            "HID: DevSrvsID:222",
            id="hid_with_serial",
        ),
        pytest.param(
            "",
            "I2C: PIIX4, address 0x70",
            "I2C: PIIX4, address 0x70",
            None,
            id="i2c",
        ),
    ],
)
async def test_device_key_stability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    serial: str,
    location: str,
    expected_suffix: str,
    reconnect_location: str | None,
) -> None:
    """Test device key format and stability across reconnects."""
    mock_config_entry.add_to_hass(hass)
    mock_openrgb_device.metadata.serial = serial
    mock_openrgb_device.metadata.location = location

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    key = next(iter(coordinator.data))
    assert key.endswith(expected_suffix)

    if reconnect_location is not None:
        mock_openrgb_device.metadata.location = reconnect_location
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert list(coordinator.data.keys()) == [key]


async def test_device_key_duplicate_hid_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    create_mock_device: Any,
) -> None:
    """Test that two identical HID devices get distinct indexed keys."""
    mock_config_entry.add_to_hass(hass)

    mock_openrgb_device.metadata.serial = ""
    mock_openrgb_device.metadata.location = "HID: DevSrvsID:111"
    mock_openrgb_device.id = 0

    second_device = create_mock_device(id=1)
    second_device.metadata.serial = ""
    second_device.metadata.location = "HID: DevSrvsID:222"

    mock_openrgb_client.devices = [mock_openrgb_device, second_device]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    keys = list(coordinator.data.keys())

    assert len(keys) == 2
    assert keys[0].endswith("hid_0")
    assert keys[1].endswith("hid_1")


@pytest.mark.parametrize(
    ("old_serial", "old_location", "expected_location", "expect_migration"),
    [
        pytest.param(
            "none", "HID: DevSrvsID:4295213270", "hid_0", True, id="hid_without_serial"
        ),
        pytest.param(
            "ABC123", "HID: DevSrvsID:111", "hid_0", True, id="hid_with_serial"
        ),
        pytest.param(
            "none",
            "I2C: PIIX4, address 0x70",
            "I2C: PIIX4, address 0x70",
            False,
            id="i2c_no_change",
        ),
        pytest.param("none", "hid_0", "hid_0", False, id="already_migrated"),
    ],
)
async def test_unique_id_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    old_serial: str,
    old_location: str,
    expected_location: str,
    expect_migration: bool,
) -> None:
    """Test unique ID migration for various location formats."""
    mock_config_entry.add_to_hass(hass)
    entry_id = mock_config_entry.entry_id

    old_uid = UID_SEPARATOR.join(
        [entry_id, "DRAM", "ENE", "ENE DRAM", old_serial, old_location]
    )
    new_uid = UID_SEPARATOR.join(
        [entry_id, "DRAM", "ENE", "ENE DRAM", old_serial, expected_location]
    )

    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, old_uid)},
        name="ENE DRAM",
    )
    entity_registry.async_get_or_create(
        "light",
        DOMAIN,
        old_uid,
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("light", DOMAIN, new_uid) is not None
    assert device_registry.async_get_device(identifiers={(DOMAIN, new_uid)}) is not None
    assert (
        entity_registry.async_get_entity_id("light", DOMAIN, old_uid) is None
    ) == expect_migration
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, old_uid)}) is None
    ) == expect_migration


async def test_unique_id_migration_duplicate_hid_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that two old HID entries with same base key get distinct indices."""
    mock_config_entry.add_to_hass(hass)
    entry_id = mock_config_entry.entry_id

    old_uid_1 = UID_SEPARATOR.join(
        [entry_id, "KEYBOARD", "Corsair", "K70", "none", "HID: DevSrvsID:111"]
    )
    old_uid_2 = UID_SEPARATOR.join(
        [entry_id, "KEYBOARD", "Corsair", "K70", "none", "HID: DevSrvsID:222"]
    )

    for old_uid in (old_uid_1, old_uid_2):
        device_registry.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, old_uid)},
            name="Corsair K70",
        )
        entity_registry.async_get_or_create(
            "light",
            DOMAIN,
            old_uid,
            config_entry=mock_config_entry,
        )

    await hass.config_entries.async_setup(entry_id)
    await hass.async_block_till_done()

    base = UID_SEPARATOR.join([entry_id, "KEYBOARD", "Corsair", "K70", "none"])
    new_uid_0 = f"{base}{UID_SEPARATOR}hid_0"
    new_uid_1 = f"{base}{UID_SEPARATOR}hid_1"

    # Both entities should exist with indexed unique IDs
    assert entity_registry.async_get_entity_id("light", DOMAIN, new_uid_0) is not None
    assert entity_registry.async_get_entity_id("light", DOMAIN, new_uid_1) is not None

    # Old unique IDs should no longer exist
    assert entity_registry.async_get_entity_id("light", DOMAIN, old_uid_1) is None
    assert entity_registry.async_get_entity_id("light", DOMAIN, old_uid_2) is None

    # Device identifiers should be migrated
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, new_uid_0)}) is not None
    )
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, new_uid_1)}) is not None
    )
