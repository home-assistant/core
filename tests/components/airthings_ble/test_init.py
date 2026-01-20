"""Test the Airthings BLE integration init."""

from copy import deepcopy

from airthings_ble import AirthingsDeviceType
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.airthings_ble.const import (
    DEFAULT_SCAN_INTERVAL,
    DEVICE_MODEL,
    DEVICE_SPECIFIC_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import (
    CORENTIUM_HOME_2_DEVICE_INFO,
    CORENTIUM_HOME_2_SERVICE_INFO,
    WAVE_DEVICE_INFO,
    WAVE_ENHANCE_DEVICE_INFO,
    WAVE_ENHANCE_SERVICE_INFO,
    WAVE_SERVICE_INFO,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("service_info", "device_info"),
    [
        (WAVE_SERVICE_INFO, WAVE_DEVICE_INFO),
        (WAVE_ENHANCE_SERVICE_INFO, WAVE_ENHANCE_DEVICE_INFO),
        (CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO),
    ],
)
async def test_migration_existing_entries(
    hass: HomeAssistant,
    service_info,
    device_info,
) -> None:
    """Test migration of existing config entry without device model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    assert DEVICE_MODEL not in entry.data

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Migration should have added device_model to entry data
    assert DEVICE_MODEL in entry.data
    assert entry.data[DEVICE_MODEL] == device_info.model.value


async def test_no_migration_when_device_model_exists(
    hass: HomeAssistant,
) -> None:
    """Test that migration does not run when device_model already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: WAVE_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(WAVE_DEVICE_INFO) as mock_update,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Should have only 1 call for initial refresh (no migration call)
    assert mock_update.call_count == 1
    assert entry.data[DEVICE_MODEL] == WAVE_DEVICE_INFO.model.value


async def test_scan_interval_corentium_home_2(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that coordinator uses radon scan interval for Corentium Home 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: CORENTIUM_HOME_2_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(CORENTIUM_HOME_2_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.airthings_corentium_home_2_123456_battery").state
            == "90"
        )

    changed_info = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    changed_info.sensors["battery"] = 89

    with patch_airthings_ble(changed_info):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.airthings_corentium_home_2_123456_battery").state
            == "90"
        )

        freezer.tick(
            DEVICE_SPECIFIC_SCAN_INTERVAL.get(
                AirthingsDeviceType.CORENTIUM_HOME_2.value
            )
            - DEFAULT_SCAN_INTERVAL
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.airthings_corentium_home_2_123456_battery").state
            == "89"
        )


@pytest.mark.parametrize(
    ("service_info", "device_info", "battery_entity_id"),
    [
        (WAVE_SERVICE_INFO, WAVE_DEVICE_INFO, "sensor.airthings_wave_123456_battery"),
        (
            WAVE_ENHANCE_SERVICE_INFO,
            WAVE_ENHANCE_DEVICE_INFO,
            "sensor.airthings_wave_enhance_123456_battery",
        ),
    ],
)
async def test_coordinator_default_scan_interval(
    hass: HomeAssistant,
    service_info,
    device_info,
    freezer: FrozenDateTimeFactory,
    battery_entity_id: str,
) -> None:
    """Test that coordinator uses default scan interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={DEVICE_MODEL: device_info.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(battery_entity_id).state == "85"

    changed_info = deepcopy(device_info)
    changed_info.sensors["battery"] = 84

    with patch_airthings_ble(changed_info):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert hass.states.get(battery_entity_id).state == "84"


@pytest.mark.parametrize(
    ("connectivity_mode", "translation_key"),
    [
        ("SmartLink", "smartlink_detected"),
        ("Not configured", "not_configured"),
    ],
)
async def test_connectivity_issue_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    connectivity_mode: str,
    translation_key: str,
) -> None:
    """Test that connectivity mode issue is created for SmartLink and NotConfigured devices."""
    device = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    device.sensors["connectivity_mode"] = connectivity_mode

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CORENTIUM_HOME_2_SERVICE_INFO.address,
        data={DEVICE_MODEL: device.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, CORENTIUM_HOME_2_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_airthings_ble(device),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    issue_id = f"connectivity_issue_{device.address}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == translation_key


@pytest.mark.parametrize(
    "connectivity_mode",
    ["Bluetooth", "Unknown", None],
)
async def test_connectivity_issue_no_trigger(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    connectivity_mode: str | None,
) -> None:
    """Test that connectivity mode issue is not created for non-SmartLink modes."""
    # Create a copy with different connectivity mode
    device = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    device.sensors["connectivity_mode"] = connectivity_mode

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CORENTIUM_HOME_2_SERVICE_INFO.address,
        data={DEVICE_MODEL: device.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, CORENTIUM_HOME_2_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_airthings_ble(device),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Check that no issue was created
    issue_id = f"connectivity_issue_{device.address}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is None


async def test_connectivity_issue_removed_on_entry_remove(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that connectivity mode issue is removed when entry is removed."""
    device = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    device.sensors["connectivity_mode"] = "SmartLink"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CORENTIUM_HOME_2_SERVICE_INFO.address,
        data={DEVICE_MODEL: device.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, CORENTIUM_HOME_2_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_airthings_ble(device),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    issue_id = f"connectivity_issue_{device.address}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # Issue should be removed
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    "new_mode",
    ["Bluetooth", "Unknown"],
)
async def test_connectivity_mode_transition_clears_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    new_mode: str,
) -> None:
    """Test that issue is removed when connectivity mode changes to BLE or unknown mode."""
    device = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    device.sensors["connectivity_mode"] = "SmartLink"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CORENTIUM_HOME_2_SERVICE_INFO.address,
        data={DEVICE_MODEL: device.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, CORENTIUM_HOME_2_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_airthings_ble(device),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        issue_id = f"connectivity_issue_{device.address}"
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

        device.sensors["connectivity_mode"] = new_mode
        coordinator = entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Issue should be removed
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_setup_ble_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test that setup fails when BLE device is not found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: WAVE_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    # BLE device not found
    with patch_async_ble_device_from_address(None):
        result = await hass.config_entries.async_setup(entry.entry_id)

    # Setup should fail and retry
    assert result is False
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_migration_update_failed(
    hass: HomeAssistant,
) -> None:
    """Test that setup fails when migration fetch fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={},  # No device_model - triggers migration
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    # Migration fetch fails
    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(side_effect=Exception("Migration failed")),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    # Setup should fail and retry
    assert result is False
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_update_data_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that coordinator handles update failures gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: WAVE_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(WAVE_DEVICE_INFO),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    battery_entity_id = "sensor.airthings_wave_123456_battery"
    state = hass.states.get(battery_entity_id)
    assert state is not None
    assert state.state == "85"

    # Now make update fail
    with patch_airthings_ble(side_effect=Exception("Update failed")):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(battery_entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
