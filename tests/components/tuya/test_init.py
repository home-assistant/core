"""Test Tuya initialization."""

from __future__ import annotations

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
)
from homeassistant.components.tuya.diagnostics import _REDACTED_DPCODES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import DEVICE_MOCKS, create_device, create_manager, initialize_entry

from tests.common import MockConfigEntry, async_load_json_object_fixture


async def test_registry_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure no-longer-present devices are removed from the device registry."""
    # Initialize with two devices
    main_manager = create_manager()
    main_device = await create_device(hass, "mcs_8yhypbo7")
    second_device = await create_device(hass, "clkg_y7j64p60glp8qpx7")
    await initialize_entry(
        hass, main_manager, mock_config_entry, [main_device, second_device]
    )

    # Initialize should have two devices
    all_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(all_entries) == 2

    # Now remove the second device from the manager and re-initialize
    del main_manager.device_map[second_device.id]
    with patch("homeassistant.components.tuya.Manager", return_value=main_manager):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Only the main device should remain
    all_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(all_entries) == 1
    assert all_entries[0].identifiers == {(DOMAIN, main_device.id)}


async def test_registry_cleanup_multiple_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure multiple config entries do not remove items from other entries."""
    main_entity_id = "sensor.boite_aux_lettres_arriere_battery"
    second_entity_id = "binary_sensor.window_downstairs_door"

    main_manager = create_manager()
    main_device = await create_device(hass, "mcs_8yhypbo7")
    await initialize_entry(hass, main_manager, mock_config_entry, main_device)

    # Ensure initial setup is correct (main present, second absent)
    assert hass.states.get(main_entity_id)
    assert entity_registry.async_get(main_entity_id)
    assert not hass.states.get(second_entity_id)
    assert not entity_registry.async_get(second_entity_id)

    # Create a second config entry
    second_config_entry = MockConfigEntry(
        title="Test Tuya entry",
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: "test_endpoint",
            CONF_TERMINAL_ID: "test_terminal",
            CONF_TOKEN_INFO: "test_token",
            CONF_USER_CODE: "test_user_code",
        },
        unique_id="56789",
    )
    second_manager = create_manager()
    second_device = await create_device(hass, "mcs_oxslv1c9")
    await initialize_entry(hass, second_manager, second_config_entry, second_device)

    # Ensure setup is correct (both present)
    assert hass.states.get(main_entity_id)
    assert entity_registry.async_get(main_entity_id)
    assert hass.states.get(second_entity_id)
    assert entity_registry.async_get(second_entity_id)


async def test_device_registry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate device registry snapshots for all devices, including unsupported ones."""

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    device_registry_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Ensure the device registry contains same amount as DEVICE_MOCKS
    assert len(device_registry_entries) == len(DEVICE_MOCKS)

    for device_registry_entry in device_registry_entries:
        assert device_registry_entry == snapshot(
            name=list(device_registry_entry.identifiers)[0][1]
        )

        # Ensure model is suffixed with "(unsupported)" when no entities are generated
        assert (" (unsupported)" in device_registry_entry.model) == (
            not er.async_entries_for_device(
                entity_registry,
                device_registry_entry.id,
                include_disabled_entities=True,
            )
        )


async def test_fixtures_valid(hass: HomeAssistant) -> None:
    """Ensure Tuya fixture files are valid."""
    # We want to ensure that the fixture files do not contain
    # `home_assistant`, `id`, or `terminal_id` keys.
    # These are provided by the Tuya diagnostics and should be removed
    # from the fixture.
    EXCLUDE_KEYS = ("home_assistant", "id", "terminal_id")

    for device_code in DEVICE_MOCKS:
        details = await async_load_json_object_fixture(
            hass, f"{device_code}.json", DOMAIN
        )
        for key in EXCLUDE_KEYS:
            assert key not in details, (
                f"Please remove data[`'{key}']` from {device_code}.json"
            )
        if "status" in details:
            statuses = details["status"]
            for key in statuses:
                if key in _REDACTED_DPCODES:
                    assert statuses[key] == "**REDACTED**", (
                        f"Please mark `data['status']['{key}']` as `**REDACTED**`"
                        f" in {device_code}.json"
                    )
