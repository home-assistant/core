"""Test the Airthings BLE integration init."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from airthings_ble import AirthingsDevice, AirthingsDeviceType
from bleak import BleakError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.airthings_ble.const import (
    CONNECTIVITY_ISSUE_PREFIX,
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
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN
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
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)

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


def _with_mode(
    device_info: AirthingsDevice, connectivity_mode: str | None
) -> AirthingsDevice:
    """Return device data reporting the given connectivity mode."""
    device_info = deepcopy(device_info)
    if connectivity_mode is None:
        del device_info.sensors["connectivity_mode"]
    else:
        device_info.sensors["connectivity_mode"] = connectivity_mode
    return device_info


async def _setup_device(
    hass: HomeAssistant,
    service_info: BluetoothServiceInfoBleak,
    device_info: AirthingsDevice,
    connectivity_mode: str | None,
) -> MockConfigEntry:
    """Set up a device reporting the given connectivity mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=service_info.address,
        data={DEVICE_MODEL: device_info.model.value},
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, service_info)

    with (
        patch_async_ble_device_from_address(service_info.device),
        patch_airthings_ble(_with_mode(device_info, connectivity_mode)),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _second_corentium_home_2() -> tuple[BluetoothServiceInfoBleak, AirthingsDevice]:
    """Return a second Corentium Home 2 with its own address and identifier."""
    address = "dd:dd:dd:dd:dd:dd"
    service_info = BluetoothServiceInfoBleak(
        name="dd-dd-dd-dd-dd-dd",
        address=address,
        device=generate_ble_device(address=address, name="Airthings Corentium Home 2"),
        rssi=-61,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
        advertisement=generate_advertisement_data(),
        connectable=True,
        time=0,
        tx_power=0,
    )
    device_info = deepcopy(CORENTIUM_HOME_2_DEVICE_INFO)
    device_info.address = address
    device_info.identifier = "654321"
    return service_info, device_info


def _issues(issue_registry: ir.IssueRegistry) -> dict[str, str | None]:
    """Return the translation key of each Airthings BLE issue by issue id."""
    return {
        issue_id: issue.translation_key
        for (domain, issue_id), issue in issue_registry.issues.items()
        if domain == DOMAIN
    }


async def _refresh_corentium_home_2(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_info: AirthingsDevice,
) -> None:
    """Run one scheduled Corentium Home 2 refresh returning the given data."""
    with patch_airthings_ble(device_info) as update_device:
        freezer.tick(
            DEVICE_SPECIFIC_SCAN_INTERVAL[AirthingsDeviceType.CORENTIUM_HOME_2.value]
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    update_device.assert_awaited_once()


@pytest.mark.parametrize(
    ("connectivity_mode", "expected_key"),
    [
        pytest.param("SmartLink", "connectivity_smartlink", id="smartlink"),
        pytest.param(
            "Not configured", "connectivity_not_configured", id="not_configured"
        ),
        pytest.param("Bluetooth", None, id="bluetooth"),
        pytest.param("unknown", None, id="unknown"),
        pytest.param(None, None, id="not_reported"),
    ],
)
async def test_connectivity_mode_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    connectivity_mode: str | None,
    expected_key: str | None,
) -> None:
    """Test an issue is created only for unsupported connectivity modes."""
    entry = await _setup_device(
        hass,
        CORENTIUM_HOME_2_SERVICE_INFO,
        CORENTIUM_HOME_2_DEVICE_INFO,
        connectivity_mode,
    )

    assert entry.state is ConfigEntryState.LOADED
    expected = (
        {f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}": expected_key}
        if expected_key
        else {}
    )
    assert _issues(issue_registry) == expected


@pytest.mark.parametrize(
    ("connectivity_mode", "translation_key"),
    [
        pytest.param("SmartLink", "connectivity_smartlink", id="smartlink"),
        pytest.param(
            "Not configured", "connectivity_not_configured", id="not_configured"
        ),
    ],
)
@pytest.mark.parametrize(
    ("service_info", "device_info", "update_interval"),
    [
        pytest.param(
            CORENTIUM_HOME_2_SERVICE_INFO,
            CORENTIUM_HOME_2_DEVICE_INFO,
            "30",
            id="corentium_home_2",
        ),
        pytest.param(
            WAVE_ENHANCE_SERVICE_INFO,
            WAVE_ENHANCE_DEVICE_INFO,
            "5",
            id="wave_enhance",
        ),
    ],
)
async def test_connectivity_mode_issue_details(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    service_info: BluetoothServiceInfoBleak,
    device_info: AirthingsDevice,
    update_interval: str,
    connectivity_mode: str,
    translation_key: str,
) -> None:
    """Test the connectivity mode issue identifies the device."""
    entry = await _setup_device(hass, service_info, device_info, connectivity_mode)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert not issue.is_fixable
    assert issue.is_persistent
    assert issue.translation_key == translation_key
    assert issue.translation_placeholders == {
        "device_name": device_info.friendly_name(),
        "serial_number": f"{device_info.model.value}{device_info.identifier}",
        "update_interval": update_interval,
        "airthings_url": "https://www.home-assistant.io/integrations/airthings",
    }


@pytest.mark.parametrize(
    ("name_by_user", "expected_name"),
    [
        pytest.param("Living room", "Living room", id="named_by_user"),
        pytest.param(None, "Airthings Corentium Home 2", id="not_named_by_user"),
    ],
)
async def test_connectivity_mode_issue_device_name(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    name_by_user: str | None,
    expected_name: str,
) -> None:
    """Test the connectivity mode issue uses the name the user gave the device."""
    entry = await _setup_device(
        hass, CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO, "SmartLink"
    )
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, CORENTIUM_HOME_2_DEVICE_INFO.address),
        entry.entry_id,
    )
    assert device is not None
    device_registry.async_update_device(device.id, name_by_user=name_by_user)

    await _refresh_corentium_home_2(
        hass, freezer, _with_mode(CORENTIUM_HOME_2_DEVICE_INFO, "SmartLink")
    )

    issue = issue_registry.async_get_issue(
        DOMAIN, f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_placeholders["device_name"] == expected_name


@pytest.mark.parametrize(
    ("initial_mode", "new_mode", "initial_key", "expected_key"),
    [
        pytest.param(
            "SmartLink",
            "Bluetooth",
            "connectivity_smartlink",
            None,
            id="smartlink_to_bluetooth",
        ),
        pytest.param(
            "Not configured",
            "Bluetooth",
            "connectivity_not_configured",
            None,
            id="not_configured_to_bluetooth",
        ),
        pytest.param(
            "Bluetooth",
            "SmartLink",
            None,
            "connectivity_smartlink",
            id="bluetooth_to_smartlink",
        ),
        pytest.param(
            "Bluetooth",
            "Not configured",
            None,
            "connectivity_not_configured",
            id="bluetooth_to_not_configured",
        ),
        pytest.param(
            "Not configured",
            "SmartLink",
            "connectivity_not_configured",
            "connectivity_smartlink",
            id="not_configured_to_smartlink",
        ),
        pytest.param(
            "SmartLink",
            "Not configured",
            "connectivity_smartlink",
            "connectivity_not_configured",
            id="smartlink_to_not_configured",
        ),
        pytest.param(
            "SmartLink",
            "unknown",
            "connectivity_smartlink",
            "connectivity_smartlink",
            id="smartlink_to_unknown",
        ),
        pytest.param(
            "SmartLink",
            None,
            "connectivity_smartlink",
            "connectivity_smartlink",
            id="smartlink_to_not_reported",
        ),
    ],
)
async def test_connectivity_mode_issue_updated_on_refresh(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    initial_mode: str,
    new_mode: str | None,
    initial_key: str | None,
    expected_key: str | None,
) -> None:
    """Test the connectivity mode issue follows the mode reported on refresh."""
    entry = await _setup_device(
        hass, CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO, initial_mode
    )
    issue_id = f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}"

    assert _issues(issue_registry) == ({issue_id: initial_key} if initial_key else {})

    await _refresh_corentium_home_2(
        hass, freezer, _with_mode(CORENTIUM_HOME_2_DEVICE_INFO, new_mode)
    )

    assert _issues(issue_registry) == ({issue_id: expected_key} if expected_key else {})


async def test_connectivity_mode_issue_kept_on_incomplete_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an incomplete read reporting Bluetooth does not delete the issue."""
    entry = await _setup_device(
        hass, CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO, "SmartLink"
    )
    incomplete = _with_mode(CORENTIUM_HOME_2_DEVICE_INFO, "Bluetooth")
    incomplete.address = ""

    await _refresh_corentium_home_2(hass, freezer, incomplete)

    assert _issues(issue_registry) == {
        f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}": "connectivity_smartlink"
    }


async def test_connectivity_mode_issue_kept_on_reload_until_removed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue survives an unreadable reload and goes with the entry."""
    entry = await _setup_device(
        hass, CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO, "SmartLink"
    )

    with patch_airthings_ble(side_effect=BleakError("Device not reachable")):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert _issues(issue_registry) == {
        f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}": "connectivity_smartlink"
    }

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert _issues(issue_registry) == {}


async def test_existing_connectivity_mode_issue_kept_when_setup_fails(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an existing issue survives a setup that cannot read the device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=CORENTIUM_HOME_2_SERVICE_INFO.address,
        data={DEVICE_MODEL: CORENTIUM_HOME_2_DEVICE_INFO.model.value},
    )
    entry.add_to_hass(hass)
    issue_id = f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}"
    placeholders = {
        "device_name": "Living room",
        "serial_number": "3250123456",
        "update_interval": "30",
        "airthings_url": "https://www.home-assistant.io/integrations/airthings",
    }
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="connectivity_smartlink",
        translation_placeholders=placeholders,
    )
    inject_bluetooth_service_info(hass, CORENTIUM_HOME_2_SERVICE_INFO)

    with (
        patch_async_ble_device_from_address(CORENTIUM_HOME_2_SERVICE_INFO.device),
        patch_airthings_ble(side_effect=BleakError("Device not reachable")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.active
    assert issue.translation_placeholders == placeholders


async def test_connectivity_mode_issue_deleted_on_remove(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the connectivity mode issue is deleted when the entry is removed."""
    entry = await _setup_device(
        hass, CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO, "SmartLink"
    )

    assert _issues(issue_registry) == {
        f"{CONNECTIVITY_ISSUE_PREFIX}{entry.entry_id}": "connectivity_smartlink"
    }

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert _issues(issue_registry) == {}


async def test_connectivity_mode_issues_are_per_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test recovering or removing one device leaves the other device's issue alone."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    first = await _setup_device(
        hass, CORENTIUM_HOME_2_SERVICE_INFO, CORENTIUM_HOME_2_DEVICE_INFO, "SmartLink"
    )
    second_service_info, second_device_info = _second_corentium_home_2()
    second = await _setup_device(
        hass, second_service_info, second_device_info, "Not configured"
    )
    first_issue = f"{CONNECTIVITY_ISSUE_PREFIX}{first.entry_id}"
    second_issue = f"{CONNECTIVITY_ISSUE_PREFIX}{second.entry_id}"
    both_issues = {
        first_issue: "connectivity_smartlink",
        second_issue: "connectivity_not_configured",
    }

    async def update_first_device(connectivity_mode: str) -> None:
        with patch_airthings_ble(
            _with_mode(CORENTIUM_HOME_2_DEVICE_INFO, connectivity_mode)
        ) as update_device:
            await hass.services.async_call(
                HA_DOMAIN,
                SERVICE_UPDATE_ENTITY,
                {ATTR_ENTITY_ID: "sensor.airthings_corentium_home_2_123456_battery"},
                blocking=True,
            )
            freezer.tick(timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN + 1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        update_device.assert_awaited_once()

    assert _issues(issue_registry) == both_issues

    await update_first_device("Bluetooth")

    assert _issues(issue_registry) == {second_issue: "connectivity_not_configured"}

    await update_first_device("SmartLink")

    assert _issues(issue_registry) == both_issues

    await hass.config_entries.async_remove(first.entry_id)
    await hass.async_block_till_done()

    assert _issues(issue_registry) == {second_issue: "connectivity_not_configured"}
