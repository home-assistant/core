"""Test the Airthings BLE integration init."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from airthings_ble import AirthingsDevice, AirthingsDeviceType
from bleak import BleakError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.airthings_ble.const import (
    DEFAULT_SCAN_INTERVAL,
    DEVICE_MODEL,
    DEVICE_SPECIFIC_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import (
    CORENTIUM_HOME_2_DEVICE_INFO,
    CORENTIUM_HOME_2_SERVICE_INFO,
    WAVE_DEVICE_INFO,
    WAVE_ENHANCE_DEVICE_INFO,
    WAVE_ENHANCE_SERVICE_INFO,
    WAVE_SERVICE_INFO,
    BluetoothServiceInfoBleak,
    patch_airthings_ble,
    patch_async_ble_device_from_address,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import inject_bluetooth_service_info

# A read that ends early leaves the address empty. The coordinator treats
# such a read as incomplete instead of creating entities from it.
INCOMPLETE_WAVE_DEVICE_INFO = deepcopy(WAVE_DEVICE_INFO)
INCOMPLETE_WAVE_DEVICE_INFO.address = ""


@pytest.mark.parametrize(
    ("service_info", "device_info"),
    [
        pytest.param(WAVE_SERVICE_INFO, WAVE_DEVICE_INFO, id="wave"),
        pytest.param(
            WAVE_ENHANCE_SERVICE_INFO, WAVE_ENHANCE_DEVICE_INFO, id="wave_enhance"
        ),
        pytest.param(
            CORENTIUM_HOME_2_SERVICE_INFO,
            CORENTIUM_HOME_2_DEVICE_INFO,
            id="corentium_home_2",
        ),
    ],
)
async def test_migration_existing_entries(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_info: BluetoothServiceInfoBleak,
    device_info: AirthingsDevice,
) -> None:
    """Test migration of an existing config entry without a device model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    scan_interval = timedelta(
        seconds=DEVICE_SPECIFIC_SCAN_INTERVAL.get(
            device_info.model.value, DEFAULT_SCAN_INTERVAL
        )
    )

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(device_info) as mock_update,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.data[DEVICE_MODEL] == device_info.model.value
        # One read for the migration and one for the first refresh.
        assert mock_update.call_count == 2

        # No poll halfway through the model's scan interval.
        freezer.tick(scan_interval / 2)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_update.call_count == 2

        # The next poll comes once the full scan interval has passed.
        freezer.tick(scan_interval / 2 + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_update.call_count == 3


async def test_setup_retries_when_device_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup is retried with a diagnostic reason when the device is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: WAVE_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    with (
        patch_async_ble_device_from_address(None),
        patch(
            "homeassistant.components.airthings_ble.coordinator.bluetooth."
            "async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        "Could not find Airthings device with address "
        f"{WAVE_SERVICE_INFO.address}: mock reachability reason" in caplog.text
    )


@pytest.mark.parametrize(
    ("entry_data", "device_info", "side_effect", "message"),
    [
        # The device answers, but the read is incomplete (no address).
        pytest.param(
            {DEVICE_MODEL: WAVE_DEVICE_INFO.model.value},
            INCOMPLETE_WAVE_DEVICE_INFO,
            None,
            "The Airthings device did not return complete data, retrying",
            id="incomplete_read",
        ),
        # The first refresh fails with a Bluetooth error.
        pytest.param(
            {DEVICE_MODEL: WAVE_DEVICE_INFO.model.value},
            None,
            BleakError("boom"),
            "Unable to fetch data: boom",
            id="update_failed",
        ),
        # An entry without a stored device model first reads the device to
        # migrate. Only that read fails; a later read would succeed.
        pytest.param(
            {},
            None,
            [BleakError("boom"), WAVE_DEVICE_INFO],
            "Unable to fetch data for migration: boom",
            id="migration_failed",
        ),
    ],
)
async def test_setup_retries_on_failed_read(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entry_data: dict[str, str],
    device_info: AirthingsDevice | None,
    side_effect: Exception | list[Exception | AirthingsDevice] | None,
    message: str,
) -> None:
    """Test setup is retried when reading the device fails or is incomplete."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data=entry_data,
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(device_info, side_effect=side_effect),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    # A failed migration read must not store a device model.
    assert entry.data == entry_data
    assert len(hass.states.async_all()) == 0
    assert message in caplog.text


@pytest.mark.parametrize(
    ("device_info", "side_effect", "message"),
    [
        pytest.param(
            None, BleakError("boom"), "Unable to fetch data: boom", id="bleak_error"
        ),
        pytest.param(
            INCOMPLETE_WAVE_DEVICE_INFO,
            None,
            "The Airthings device did not return complete data, retrying",
            id="incomplete_read",
        ),
    ],
)
async def test_sensors_unavailable_while_update_fails(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    device_info: AirthingsDevice | None,
    side_effect: Exception | None,
    message: str,
) -> None:
    """Test sensors become unavailable when an update fails and recover after."""
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

    entity_id = "sensor.airthings_wave_123456_battery"
    assert hass.states.get(entity_id).state == "85"

    with patch_airthings_ble(device_info, side_effect=side_effect):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert message in caplog.text

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    with patch_airthings_ble(WAVE_DEVICE_INFO):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "85"


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


async def test_device_registry_sw_version_updates_on_refresh(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the device firmware version follows a firmware upgrade."""
    first_device = deepcopy(WAVE_DEVICE_INFO)
    second_device = deepcopy(WAVE_DEVICE_INFO)
    first_device.sw_version = "G-BLE-1.5.3-master+0"
    second_device.sw_version = "G-BLE-2.2.3-master+0"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        data={DEVICE_MODEL: first_device.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, WAVE_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(WAVE_SERVICE_INFO.device),
        patch_airthings_ble(side_effect=[first_device, second_device]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device = device_registry.async_get_device_by_connection(
            (dr.CONNECTION_BLUETOOTH, WAVE_DEVICE_INFO.address), entry.entry_id
        )
        assert device is not None
        assert device.sw_version == "G-BLE-1.5.3-master+0"

        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.sw_version == "G-BLE-2.2.3-master+0"


async def _setup_corentium_home_2(
    hass: HomeAssistant, connectivity_mode: str | None
) -> MockConfigEntry:
    """Set up a Corentium Home 2 reporting the given connectivity mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CORENTIUM_HOME_2_SERVICE_INFO.address,
        data={DEVICE_MODEL: CORENTIUM_HOME_2_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, CORENTIUM_HOME_2_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_airthings_ble(_corentium_home_2_with_mode(connectivity_mode)),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _corentium_home_2_with_mode(connectivity_mode: str | None):
    """Return Corentium Home 2 data reporting the given connectivity mode."""
    device_info = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    if connectivity_mode is None:
        del device_info.sensors["connectivity_mode"]
    else:
        device_info.sensors["connectivity_mode"] = connectivity_mode
    return device_info


def _issue_translation_keys(issue_registry: ir.IssueRegistry) -> list[str | None]:
    """Return the translation keys of the Airthings BLE issues."""
    return [
        issue.translation_key
        for (domain, _), issue in issue_registry.issues.items()
        if domain == DOMAIN
    ]


@pytest.mark.parametrize(
    ("connectivity_mode", "expected_issues"),
    [
        ("SmartLink", ["smartlink"]),
        ("Not configured", ["not_configured"]),
        ("Bluetooth", []),
        ("unknown", []),
        (None, []),
    ],
)
async def test_connectivity_mode_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    connectivity_mode: str | None,
    expected_issues: list[str],
) -> None:
    """Test an issue is created only for unsupported connectivity modes."""
    entry = await _setup_corentium_home_2(hass, connectivity_mode)

    assert entry.state is ConfigEntryState.LOADED
    assert _issue_translation_keys(issue_registry) == expected_issues


async def test_connectivity_mode_issue_details(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the connectivity mode issue identifies the device."""
    entry = await _setup_corentium_home_2(hass, "SmartLink")

    issue = issue_registry.async_get_issue(
        DOMAIN, f"connectivity_mode_{entry.entry_id}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert not issue.is_fixable
    assert issue.translation_placeholders == {
        "device_name": "Airthings Corentium Home 2",
        "serial_number": f"{CORENTIUM_HOME_2_DEVICE_INFO.model.value}123456",
        "update_interval": "30",
    }


@pytest.mark.parametrize(
    ("initial_mode", "new_mode", "expected_issues"),
    [
        ("SmartLink", "Bluetooth", []),
        ("Not configured", "Bluetooth", []),
        ("Not configured", "SmartLink", ["smartlink"]),
        ("SmartLink", "unknown", ["smartlink"]),
        ("SmartLink", None, ["smartlink"]),
    ],
)
async def test_connectivity_mode_issue_updated_on_refresh(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    initial_mode: str,
    new_mode: str | None,
    expected_issues: list[str],
) -> None:
    """Test the connectivity mode issue follows the mode reported on refresh."""
    await _setup_corentium_home_2(hass, initial_mode)

    assert len(_issue_translation_keys(issue_registry)) == 1

    with patch_airthings_ble(_corentium_home_2_with_mode(new_mode)):
        freezer.tick(
            DEVICE_SPECIFIC_SCAN_INTERVAL[AirthingsDeviceType.CORENTIUM_HOME_2.value]
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert _issue_translation_keys(issue_registry) == expected_issues


async def test_connectivity_mode_issue_deleted_on_unload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the connectivity mode issue is deleted when the entry is unloaded."""
    entry = await _setup_corentium_home_2(hass, "SmartLink")

    assert _issue_translation_keys(issue_registry) == ["smartlink"]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert _issue_translation_keys(issue_registry) == []


async def test_connectivity_mode_issue_deleted_after_refresh_during_unload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a refresh finishing while the entry unloads leaves no issue behind."""
    entry = await _setup_corentium_home_2(hass, "Bluetooth")
    release_update = asyncio.Event()
    update_done = asyncio.Event()
    unload_platforms = hass.config_entries.async_unload_platforms

    async def _delayed_update(*_):
        await release_update.wait()
        update_done.set()
        return _corentium_home_2_with_mode("SmartLink")

    async def _unload_platforms_during_update(*args):
        release_update.set()
        await update_done.wait()
        return await unload_platforms(*args)

    with (
        patch_airthings_ble(side_effect=_delayed_update),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            side_effect=_unload_platforms_during_update,
        ),
    ):
        freezer.tick(
            DEVICE_SPECIFIC_SCAN_INTERVAL[AirthingsDeviceType.CORENTIUM_HOME_2.value]
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert _issue_translation_keys(issue_registry) == []


async def test_connectivity_mode_issue_not_created_by_update_after_unload(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a manual update finishing after unload does not create an issue."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    entry = await _setup_corentium_home_2(hass, "Bluetooth")
    release_update = asyncio.Event()

    async def _delayed_update(*_):
        await release_update.wait()
        return _corentium_home_2_with_mode("SmartLink")

    with patch_airthings_ble(side_effect=_delayed_update):
        update = hass.async_create_task(
            hass.services.async_call(
                HA_DOMAIN,
                SERVICE_UPDATE_ENTITY,
                {ATTR_ENTITY_ID: "sensor.airthings_corentium_home_2_123456_battery"},
                blocking=True,
            )
        )
        await asyncio.sleep(0)

        assert await hass.config_entries.async_unload(entry.entry_id)

        release_update.set()
        await update
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert _issue_translation_keys(issue_registry) == []
