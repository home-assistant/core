"""Test Tuya initialization."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_device_handlers import TUYA_QUIRKS_REGISTRY
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
)
from homeassistant.components.tuya.diagnostics import _REDACTED_DPCODES
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    DEVICE_MOCKS,
    TuyaNotificationHelper,
    create_device,
    create_manager,
    initialize_entry,
)

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
    with patch(
        "homeassistant.components.tuya.coordinator.Manager", return_value=main_manager
    ):
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


@pytest.mark.usefixtures("no_quirk")
async def test_device_registry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate device registry snapshots for all devices."""

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


@pytest.mark.parametrize(
    ("mock_device_code", "platforms", "manufacturer", "model", "model_id", "quirks"),
    [
        # Ensure model is suffixed with "(unsupported)" when no entities
        # are generated
        (
            "mal_gyitctrjj1kefxp2",
            [],
            "Tuya",
            "Multifunction alarm (unsupported)",
            "gyitctrjj1kefxp2",
            {},
        ),
        # Ensure model is not suffixed with "(unsupported)" when entities
        # are generated
        (
            "mal_gyitctrjj1kefxp2",
            [Platform.ALARM_CONTROL_PANEL],
            "Tuya",
            "Multifunction alarm",
            "gyitctrjj1kefxp2",
            {},
        ),
        # With a quirk that has manufacturer, model and model_id are
        # taken from quirk (and not suffixed with "(unsupported)" even if
        # no entities are generated)
        (
            "mal_gyitctrjj1kefxp2",
            [],
            "My manufacturer",
            "Amazing model",
            "AMA-ZING1",
            {
                "gyitctrjj1kefxp2": MagicMock(
                    manufacturer="My manufacturer",
                    model="Amazing model",
                    model_id="AMA-ZING1",
                )
            },
        ),
        # With a quirk that has manufacturer, model and model_id are
        # taken from quirk (even if None)
        (
            "mal_gyitctrjj1kefxp2",
            [],
            "My manufacturer",
            None,
            None,
            {
                "gyitctrjj1kefxp2": MagicMock(
                    manufacturer="My manufacturer",
                    model=None,
                    model_id=None,
                )
            },
        ),
        # With a quirk that has null manufacturer, model and model_id
        # are ignored
        (
            "mal_gyitctrjj1kefxp2",
            [],
            "Tuya",
            "Multifunction alarm (unsupported)",
            "gyitctrjj1kefxp2",
            {
                "gyitctrjj1kefxp2": MagicMock(
                    manufacturer=None,
                    model="Amazing model",
                    model_id="AMA-ZING1",
                )
            },
        ),
    ],
)
async def test_device_registry_with_quirk(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
    platforms: list[Platform],
    manufacturer: str,
    model: str | None,
    model_id: str | None,
    quirks: dict[str, MagicMock],
) -> None:
    """Validate device information with and without quirks."""

    with (
        patch.dict(TUYA_QUIRKS_REGISTRY._quirks, quirks, clear=True),
        patch("homeassistant.components.tuya.coordinator.register_tuya_quirks"),
        patch("homeassistant.components.tuya.PLATFORMS", platforms),
    ):
        await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    device_registry_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_registry_entries) == 1
    device_registry_entry = device_registry_entries[0]

    assert device_registry_entry.manufacturer == manufacturer
    assert device_registry_entry.model == model
    assert device_registry_entry.model_id == model_id
    assert device_registry_entry.name == "Multifunction alarm"


@patch.object(
    TUYA_QUIRKS_REGISTRY,
    "initialise_device_quirk",
    wraps=TUYA_QUIRKS_REGISTRY.initialise_device_quirk,
)
@patch("homeassistant.components.tuya.PLATFORMS", [])
async def test_dynamic_add_device(
    mock_initialise_device_quirk: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_manager: Manager,
    notification_helper: TuyaNotificationHelper,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure add device event works correctly.

    - the device should be added to the device registry
    even if there are no platforms (i.e. no entities created)
    - the device should have the quirk applied
    """
    main_device = await create_device(hass, "mcs_8yhypbo7")
    second_device = await create_device(hass, "clkg_y7j64p60glp8qpx7")

    # Initialize with a single device
    await initialize_entry(hass, mock_manager, mock_config_entry, [main_device])

    # Should now have one device in the registry
    all_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(all_entries) == 1
    assert any(
        (DOMAIN, main_device.id) in device_registry_entry.identifiers
        for device_registry_entry in all_entries
    )
    mock_initialise_device_quirk.assert_called_once_with(main_device)

    # Trigger add second device from the manager
    mock_initialise_device_quirk.reset_mock()
    await notification_helper.async_send_add_device(second_device)

    # Should now have two devices in the registry
    all_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(all_entries) == 2
    assert any(
        (DOMAIN, main_device.id) in device_registry_entry.identifiers
        for device_registry_entry in all_entries
    )
    assert any(
        (DOMAIN, second_device.id) in device_registry_entry.identifiers
        for device_registry_entry in all_entries
    )
    mock_initialise_device_quirk.assert_called_once_with(second_device)


async def test_dynamic_remove_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_manager: Manager,
    notification_helper: TuyaNotificationHelper,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure remove device event works correctly."""
    # Initialize with two devices
    main_device = await create_device(hass, "mcs_8yhypbo7")
    second_device = await create_device(hass, "clkg_y7j64p60glp8qpx7")
    await initialize_entry(
        hass, mock_manager, mock_config_entry, [main_device, second_device]
    )
    all_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(all_entries) == 2

    # Trigger remove second device from the manager
    await notification_helper.async_send_remove_device(second_device)

    # Only the main device should remain
    all_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(all_entries) == 1
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, main_device.id)})
        in all_entries
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
        expected_code = f"{details['category']}_{details['product_id']}"
        assert device_code == expected_code, (
            f"Device code {device_code} does not match expected {expected_code}"
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
