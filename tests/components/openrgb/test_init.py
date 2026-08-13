"""Tests for the OpenRGB integration init."""

import copy
import socket
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from openrgb.utils import ControllerParsingError, OpenRGBDisconnected, SDKVersionError
import pytest

from homeassistant.components.openrgb import async_remove_config_entry_device
from homeassistant.components.openrgb.const import DOMAIN, SCAN_INTERVAL, UID_SEPARATOR
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
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
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that server device cannot be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    server_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
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
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that connected devices cannot be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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
    server_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )
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
        via_device_id=server_device.id,
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
    server_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry_id), entry_id
    )

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
        via_device_id=server_device.id,
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


def _light_unique_ids(
    entity_registry: er.EntityRegistry, entry: MockConfigEntry
) -> set[str]:
    """Return the unique ids of every light registered for the entry."""
    return {
        registry_entry.unique_id
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if registry_entry.domain == Platform.LIGHT
    }


def _device_at(device: MagicMock, serial: str, location: str) -> MagicMock:
    """Return a copy of the mocked device with the given serial and location."""
    copied = copy.deepcopy(device)
    copied.metadata.serial = serial
    copied.metadata.location = location
    return copied


def _key(entry: MockConfigEntry, serial: str, location: str) -> str:
    """Build a device key for the mocked device."""
    return UID_SEPARATOR.join(
        [entry.entry_id, "DRAM", "ENE", "ENE SMBus Device", serial, location]
    )


@pytest.mark.parametrize(
    ("location", "expected_location"),
    [
        ("HID: /dev/hidraw14", "hid"),
        # USB locations are libusb bus paths and move the same way
        ("USB: 1-8.2.2.1.1", "usb"),
    ],
)
async def test_device_key_replaces_unstable_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    entity_registry: er.EntityRegistry,
    location: str,
    expected_location: str,
) -> None:
    """Test that an unstable connection path is replaced given a serial."""
    mock_openrgb_client.devices = [
        _device_at(mock_openrgb_device, "IO2105F28204577", location)
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _light_unique_ids(entity_registry, mock_config_entry) == {
        _key(mock_config_entry, "IO2105F28204577", expected_location)
    }


async def test_device_key_keeps_padded_serial_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a serial of only padding is treated as not reported.

    Some controllers answer a serial request with padding when the hardware
    cannot supply one, which must not be mistaken for a real serial.
    """
    mock_openrgb_client.devices = [
        _device_at(mock_openrgb_device, "        ", "HID: /dev/hidraw14")
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _light_unique_ids(entity_registry, mock_config_entry) == {
        _key(mock_config_entry, "none", "HID: /dev/hidraw14")
    }


@pytest.mark.parametrize("serial", ["", "SERIAL123"])
async def test_device_key_keeps_i2c_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    entity_registry: er.EntityRegistry,
    serial: str,
) -> None:
    """Test that locations on other buses are left untouched.

    Only HID and USB connection paths are reassigned, so devices on other buses
    keep the key they already have. The case with a serial matters: without it
    the replacement is skipped anyway and the test would pass even if I2C
    locations were being replaced.
    """
    location = "I2C: PIIX4, address 0x70"
    mock_openrgb_client.devices = [_device_at(mock_openrgb_device, serial, location)]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _light_unique_ids(entity_registry, mock_config_entry) == {
        _key(mock_config_entry, serial or "none", location)
    }


async def test_device_key_survives_changed_connection_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that unchanged hardware keeps its identity on a new path.

    Connection paths are reassigned when a device reconnects and on every
    reboot, which previously registered the device again as a duplicate.
    """
    device = _device_at(mock_openrgb_device, "IO2105F28204577", "HID: /dev/hidraw14")
    mock_openrgb_client.devices = [device]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_ids_before = _light_unique_ids(entity_registry, mock_config_entry)
    assert len(unique_ids_before) == 1

    # Same hardware, reconnected on a different path
    device.metadata.location = "HID: /dev/hidraw31"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _light_unique_ids(entity_registry, mock_config_entry) == unique_ids_before


async def test_migrate_hid_device_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that already registered keys drop the HID connection path."""
    mock_openrgb_client.devices = [
        _device_at(mock_openrgb_device, "IO2105F28204577", "HID: /dev/hidraw31")
    ]

    mock_config_entry.add_to_hass(hass)

    # Registered by version 1, on a path that has since changed
    legacy_key = _key(mock_config_entry, "IO2105F28204577       ", "HID: /dev/hidraw14")
    legacy_entity = entity_registry.async_get_or_create(
        Platform.LIGHT, DOMAIN, legacy_key, config_entry=mock_config_entry
    )
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, legacy_key)},
    )
    foreign_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", legacy_key)},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    stable_key = _key(mock_config_entry, "IO2105F28204577", "hid")

    # The existing entity was reused rather than replaced by a duplicate
    migrated = entity_registry.async_get(legacy_entity.entity_id)
    assert migrated
    assert migrated.unique_id == stable_key
    assert _light_unique_ids(entity_registry, mock_config_entry) == {stable_key}

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, stable_key), mock_config_entry.entry_id
    )
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, legacy_key), mock_config_entry.entry_id
    )

    # Identifiers owned by another integration are left untouched
    assert device_registry.async_get_device_by_identifier(
        ("other_domain", legacy_key), mock_config_entry.entry_id
    ) == device_registry.async_get(foreign_device.id)

    # The migration ran once and will not run again
    assert mock_config_entry.version == 2


@pytest.mark.parametrize(
    ("legacy_serial", "legacy_location"),
    [
        # No serial, so the HID path is still the only discriminator
        ("none", "HID: /dev/hidraw14"),
        ("none", "USB: 1-8.2.2.1.1"),
        # Another bus, whose location is stable
        ("none", "I2C: PIIX4, address 0x70"),
        ("SERIAL123", "I2C: PIIX4, address 0x70"),
    ],
)
@pytest.mark.usefixtures("mock_openrgb_client")
async def test_migrate_leaves_other_keys_alone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    legacy_serial: str,
    legacy_location: str,
) -> None:
    """Test that only HID and USB keys with a serial are rewritten."""
    mock_config_entry.add_to_hass(hass)

    legacy_key = _key(mock_config_entry, legacy_serial, legacy_location)
    legacy_entity = entity_registry.async_get_or_create(
        Platform.LIGHT, DOMAIN, legacy_key, config_entry=mock_config_entry
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    untouched = entity_registry.async_get(legacy_entity.entity_id)
    assert untouched
    assert untouched.unique_id == legacy_key
    assert mock_config_entry.version == 2


async def test_migrate_keeps_existing_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that migration does not collide with an existing registration.

    A duplicate registered before the fix may already occupy the stable key, so
    the legacy entry has to be left alone instead of failing the migration.
    """
    mock_openrgb_client.devices = [
        _device_at(mock_openrgb_device, "IO2105F28204577", "HID: /dev/hidraw14")
    ]

    mock_config_entry.add_to_hass(hass)

    stable_key = _key(mock_config_entry, "IO2105F28204577", "hid")
    legacy_key = _key(mock_config_entry, "IO2105F28204577       ", "HID: /dev/hidraw14")
    entity_registry.async_get_or_create(
        Platform.LIGHT, DOMAIN, stable_key, config_entry=mock_config_entry
    )
    legacy_entity = entity_registry.async_get_or_create(
        Platform.LIGHT, DOMAIN, legacy_key, config_entry=mock_config_entry
    )
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, stable_key)},
    )
    legacy_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, legacy_key)},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    untouched = entity_registry.async_get(legacy_entity.entity_id)
    assert untouched
    assert untouched.unique_id == legacy_key

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, legacy_key), mock_config_entry.entry_id
    ) == device_registry.async_get(legacy_device.id)


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_migrate_ignores_non_device_keys(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that keys which are not device keys are left alone.

    The SDK server device and the profile select entity do not carry a
    location, so they are not in the six part device shape.
    """
    mock_config_entry.add_to_hass(hass)

    profile_key = UID_SEPARATOR.join([mock_config_entry.entry_id, "profile"])
    profile_entity = entity_registry.async_get_or_create(
        Platform.SELECT, DOMAIN, profile_key, config_entry=mock_config_entry
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    untouched = entity_registry.async_get(profile_entity.entity_id)
    assert untouched
    assert untouched.unique_id == profile_key


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_migrate_skipped_for_current_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an entry already on the current version is not migrated."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, version=2)

    legacy_key = _key(mock_config_entry, "IO2105F28204577", "HID: /dev/hidraw14")
    legacy_entity = entity_registry.async_get_or_create(
        Platform.LIGHT, DOMAIN, legacy_key, config_entry=mock_config_entry
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    untouched = entity_registry.async_get(legacy_entity.entity_id)
    assert untouched
    assert untouched.unique_id == legacy_key


async def test_migrate_device_with_two_openrgb_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that every identifier on one device is migrated.

    A device carrying more than one identifier must be updated once with all of
    the replacements, otherwise each write reverts the previous one.
    """
    mock_openrgb_client.devices = [
        _device_at(mock_openrgb_device, "IO2105F28204577", "HID: /dev/hidraw14")
    ]

    mock_config_entry.add_to_hass(hass)

    first = _key(mock_config_entry, "IO2105F28204577", "HID: /dev/hidraw14")
    second = _key(mock_config_entry, "382042V02105657", "USB: 1-8.2.2.1.1")
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, first), (DOMAIN, second)},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for serial, bus in (("IO2105F28204577", "hid"), ("382042V02105657", "usb")):
        assert device_registry.async_get_device_by_identifier(
            (DOMAIN, _key(mock_config_entry, serial, bus)),
            mock_config_entry.entry_id,
        ), f"{serial} was not migrated"

    for stale in (first, second):
        assert not device_registry.async_get_device_by_identifier(
            (DOMAIN, stale), mock_config_entry.entry_id
        )


async def test_device_key_treats_reserved_serial_as_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a serial of "none" is treated as not reported.

    "none" is what the key builder writes for a value the device did not report,
    so it cannot also act as one. Reading it both ways would make setup and
    migration disagree and register the device twice.
    """
    mock_openrgb_client.devices = [
        _device_at(mock_openrgb_device, "none", "HID: /dev/hidraw14")
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The location is kept, exactly as the migration leaves such a key
    assert _light_unique_ids(entity_registry, mock_config_entry) == {
        _key(mock_config_entry, "none", "HID: /dev/hidraw14")
    }
