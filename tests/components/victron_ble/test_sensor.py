"""Test updating sensors in the victron_ble integration."""

import json
import time

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth.passive_update_processor import (
    serialize_entity_description,
)
from homeassistant.components.victron_ble.const import (
    DOMAIN,
    REAUTH_AFTER_FAILURES,
    VICTRON_IDENTIFIER,
)
from homeassistant.components.victron_ble.sensor import SENSOR_DESCRIPTIONS
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .fixtures import (
    VICTRON_AC_CHARGER_SERVICE_INFO,
    VICTRON_AC_CHARGER_TOKEN,
    VICTRON_BATTERY_MONITOR_SERVICE_INFO,
    VICTRON_BATTERY_MONITOR_TOKEN,
    VICTRON_BATTERY_SENSE_SERVICE_INFO,
    VICTRON_BATTERY_SENSE_TOKEN,
    VICTRON_DC_DC_CONVERTER_SERVICE_INFO,
    VICTRON_DC_DC_CONVERTER_TOKEN,
    VICTRON_DC_DC_CONVERTER_UNKNOWN_OFF_REASON_SERVICE_INFO,
    VICTRON_DC_ENERGY_METER_SERVICE_INFO,
    VICTRON_DC_ENERGY_METER_TOKEN,
    VICTRON_SMART_BATTERY_PROTECT_SERVICE_INFO,
    VICTRON_SMART_BATTERY_PROTECT_TOKEN,
    VICTRON_SMART_LITHIUM_SERVICE_INFO,
    VICTRON_SMART_LITHIUM_TOKEN,
    VICTRON_SOLAR_CHARGER_SERVICE_INFO,
    VICTRON_SOLAR_CHARGER_TOKEN,
    VICTRON_VEBUS_BAD_KEY_SERVICE_INFO,
    VICTRON_VEBUS_SERVICE_INFO,
    VICTRON_VEBUS_TOKEN,
    VICTRON_VEBUS_UNRECOGNIZED_MODE_SERVICE_INFO,
)

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source_connectable,
    inject_bluetooth_service_info,
)

# Crafted solar charger advertisements with specific charger_error values.
# These are real encrypted payloads using VICTRON_SOLAR_CHARGER_TOKEN.
SOLAR_CHARGER_ERROR_PAYLOADS = {
    # ChargerError.NO_ERROR -> state "no_error"
    "no_error": "100242a0016207adceb37b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
    # ChargerError.INTERNAL_SUPPLY_A -> mapped to state "internal_supply"
    "internal_supply": "100242a0016207adce787b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
    # ChargerError.VOLTAGE_HIGH -> state "voltage_high"
    "voltage_high": "100242a0016207adceb17b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
    # ChargerError.NETWORK_A -> mapped to state "network"
    "network": "100242a0016207adcef77b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
}


def test_sensor_descriptions_are_json_serializable() -> None:
    """Ensure entity descriptions contain no non-JSON-serializable fields.

    The passive Bluetooth processor persists entity descriptions to storage
    between HA restarts via serialize_entity_description(). Fields that are
    Python callables (e.g. a value_fn lambda) cannot be serialized and cause
    repeated 'Bad data' errors in the homeassistant.helpers.storage logger.

    Regression test for https://github.com/home-assistant/core/issues/167224
    """
    for key, description in SENSOR_DESCRIPTIONS.items():
        serialized = serialize_entity_description(description)
        try:
            json.dumps(serialized)
        except TypeError as err:
            raise AssertionError(
                f"SENSOR_DESCRIPTIONS[{key!r}] produced a non-serializable value: {err}"
            ) from err


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    (
        "service_info",
        "access_token",
    ),
    [
        (VICTRON_AC_CHARGER_SERVICE_INFO, VICTRON_AC_CHARGER_TOKEN),
        (VICTRON_BATTERY_MONITOR_SERVICE_INFO, VICTRON_BATTERY_MONITOR_TOKEN),
        (VICTRON_BATTERY_SENSE_SERVICE_INFO, VICTRON_BATTERY_SENSE_TOKEN),
        (VICTRON_DC_DC_CONVERTER_SERVICE_INFO, VICTRON_DC_DC_CONVERTER_TOKEN),
        (VICTRON_DC_ENERGY_METER_SERVICE_INFO, VICTRON_DC_ENERGY_METER_TOKEN),
        (
            VICTRON_SMART_BATTERY_PROTECT_SERVICE_INFO,
            VICTRON_SMART_BATTERY_PROTECT_TOKEN,
        ),
        (VICTRON_SMART_LITHIUM_SERVICE_INFO, VICTRON_SMART_LITHIUM_TOKEN),
        (VICTRON_SOLAR_CHARGER_SERVICE_INFO, VICTRON_SOLAR_CHARGER_TOKEN),
        (VICTRON_VEBUS_SERVICE_INFO, VICTRON_VEBUS_TOKEN),
    ],
    ids=[
        "ac_charger",
        "battery_monitor",
        "battery_sense",
        "dc_dc_converter",
        "dc_energy_meter",
        "smart_battery_protect",
        "smart_lithium",
        "solar_charger",
        "vebus",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry_added_to_hass: MockConfigEntry,
    service_info: BluetoothServiceInfo,
    access_token: str,
) -> None:
    """Test sensor entities."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Initially no entities should be created until bluetooth data is received
    assert len(hass.states.async_all()) == 0

    # Inject bluetooth service info to trigger entity creation
    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    # Use snapshot testing to verify all entity states and registry entries
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


def _inject_bad_advertisement(hass: HomeAssistant, seq: int = 0) -> None:
    """Inject a VEBus advertisement that will fail decryption.

    Each call uses a unique payload suffix to avoid deduplication by the
    bluetooth manager, while keeping the VEBus device type header intact.
    """
    info = VICTRON_VEBUS_BAD_KEY_SERVICE_INFO
    # Vary the last byte so each injection is unique
    raw = bytearray(info.manufacturer_data[VICTRON_IDENTIFIER])
    raw[-1] = seq & 0xFF
    device = generate_ble_device(address=info.address, name=info.name, details={})
    adv = generate_advertisement_data(
        local_name=info.name,
        manufacturer_data={VICTRON_IDENTIFIER: bytes(raw)},
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        rssi=-60,
    )
    inject_advertisement_with_time_and_source_connectable(
        hass, device, adv, time.monotonic(), "local", True
    )


def _inject_unrecognized_mode_advertisement(hass: HomeAssistant, seq: int = 0) -> None:
    """Inject a Victron advertisement with an unrecognized mode byte.

    detect_device_type returns None for this payload so the reauth guard
    must treat it as neutral (neither increment nor reset the failure counter).
    """
    info = VICTRON_VEBUS_UNRECOGNIZED_MODE_SERVICE_INFO
    raw = bytearray(info.manufacturer_data[VICTRON_IDENTIFIER])
    raw[-1] = seq & 0xFF
    device = generate_ble_device(address=info.address, name=info.name, details={})
    adv = generate_advertisement_data(
        local_name=info.name,
        manufacturer_data={VICTRON_IDENTIFIER: bytes(raw)},
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        rssi=-60,
    )
    inject_advertisement_with_time_and_source_connectable(
        hass, device, adv, time.monotonic(), "local", True
    )


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_triggered_after_consecutive_failures(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test that reauth is triggered after consecutive decryption failures."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Inject bad advertisements (device type recognized but decryption fails).
    # Each call uses a unique payload suffix to avoid bluetooth manager deduplication.
    for i in range(REAUTH_AFTER_FAILURES):
        _inject_bad_advertisement(hass, seq=i)
        await hass.async_block_till_done()

    # Reauth flow should have been triggered
    flows = hass.config_entries.flow.async_progress_by_handler("victron_ble")
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_not_triggered_on_successful_decrypt(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test that reauth is not triggered when decryption succeeds."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Inject bad advertisements, but fewer than the threshold
    for i in range(REAUTH_AFTER_FAILURES - 1):
        _inject_bad_advertisement(hass, seq=i)
        await hass.async_block_till_done()

    # Then inject a good advertisement to reset the counter
    inject_bluetooth_service_info(hass, VICTRON_VEBUS_SERVICE_INFO)
    await hass.async_block_till_done()

    # No reauth should have been triggered
    flows = hass.config_entries.flow.async_progress_by_handler("victron_ble")
    assert len(flows) == 0


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_triggered_only_once(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test that reauth is only triggered once per failure streak."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Inject many bad advertisements
    for i in range(REAUTH_AFTER_FAILURES + 5):
        _inject_bad_advertisement(hass, seq=i)
        await hass.async_block_till_done()

    # Still only one reauth flow
    flows = hass.config_entries.flow.async_progress_by_handler("victron_ble")
    assert len(flows) == 1


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_not_triggered_on_unknown_enum_value(
    hass: HomeAssistant,
) -> None:
    """Test reauth is NOT triggered when a valid key yields a sparse update.

    Some devices report bitmask combinations for OffReason or AlarmReason that
    are not in the enum (e.g. NO_INPUT_POWER|ENGINE_SHUTDOWN = 0x81 on a DC-DC
    converter that stopped due to both conditions simultaneously). The parser
    raises ValueError, producing a sparse update (signal strength only).
    This must not be mistaken for a wrong encryption key.

    Regression test for https://github.com/home-assistant/core/issues/167105
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": VICTRON_DC_DC_CONVERTER_UNKNOWN_OFF_REASON_SERVICE_INFO.address,
            CONF_ACCESS_TOKEN: VICTRON_DC_DC_CONVERTER_TOKEN,
        },
        unique_id=VICTRON_DC_DC_CONVERTER_UNKNOWN_OFF_REASON_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_info = VICTRON_DC_DC_CONVERTER_UNKNOWN_OFF_REASON_SERVICE_INFO
    for idx in range(REAUTH_AFTER_FAILURES + 1):
        inject_bluetooth_service_info(
            hass,
            BluetoothServiceInfo(
                name=service_info.name,
                address=service_info.address,
                rssi=service_info.rssi - idx,
                manufacturer_data=service_info.manufacturer_data,
                service_data=service_info.service_data,
                service_uuids=service_info.service_uuids,
                source=service_info.source,
            ),
        )
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    ("payload_hex", "expected_state"),
    [
        (SOLAR_CHARGER_ERROR_PAYLOADS["no_error"], "no_error"),
        (SOLAR_CHARGER_ERROR_PAYLOADS["internal_supply"], "internal_supply"),
        (SOLAR_CHARGER_ERROR_PAYLOADS["voltage_high"], "voltage_high"),
        (SOLAR_CHARGER_ERROR_PAYLOADS["network"], "network"),
    ],
    ids=["no_error", "internal_supply_variant", "voltage_high", "network_variant"],
)
async def test_charger_error_state(
    hass: HomeAssistant,
    payload_hex: str,
    expected_state: str,
) -> None:
    """Test that charger error values are correctly mapped to sensor states."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: VICTRON_SOLAR_CHARGER_TOKEN},
        unique_id=VICTRON_SOLAR_CHARGER_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_info = BluetoothServiceInfo(
        name="Solar Charger",
        address=VICTRON_SOLAR_CHARGER_SERVICE_INFO.address,
        rssi=-60,
        manufacturer_data={VICTRON_IDENTIFIER: bytes.fromhex(payload_hex)},
        service_data={},
        service_uuids=[],
        source="local",
    )

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solar_charger_charger_error")
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_not_triggered_on_unrecognized_mode(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test reauth is NOT triggered by advertisements with unrecognized mode bytes.

    Some Victron devices broadcast advertisements with mode bytes that
    detect_device_type does not recognize (returns None).
    validate_advertisement_key also returns False for these, but that does
    not mean the encryption key is wrong.

    Regression test for https://github.com/home-assistant/core/issues/168019
    """
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # First inject a valid advertisement so update.devices is populated
    inject_bluetooth_service_info(hass, VICTRON_VEBUS_SERVICE_INFO)
    await hass.async_block_till_done()

    # Now send many unrecognized-mode advertisements
    for i in range(REAUTH_AFTER_FAILURES + 5):
        _inject_unrecognized_mode_advertisement(hass, seq=i)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_still_triggers_across_unrecognized_mode(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test that unrecognized-mode advertisements are neutral for the failure counter.

    The sequence bad → bad → unrecognized → bad must still trigger reauth
    because unrecognized advertisements should neither increment nor reset the
    consecutive failure counter.

    Regression test for https://github.com/home-assistant/core/issues/168019
    """
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # First inject a valid advertisement so update.devices is populated
    inject_bluetooth_service_info(hass, VICTRON_VEBUS_SERVICE_INFO)
    await hass.async_block_till_done()

    # bad, bad (2 failures)
    _inject_bad_advertisement(hass, seq=100)
    await hass.async_block_till_done()
    _inject_bad_advertisement(hass, seq=101)
    await hass.async_block_till_done()

    # unrecognized mode — should be neutral
    _inject_unrecognized_mode_advertisement(hass, seq=50)
    await hass.async_block_till_done()

    # one more bad → 3 consecutive failures → reauth
    _inject_bad_advertisement(hass, seq=102)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
