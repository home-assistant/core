"""Tests for diagnostics.py."""

from unittest.mock import MagicMock

from homeassistant.components.bluetti import BluettiRuntimeData
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.bluetti.models import BluettiDevice
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics_redacts_sensitive_data_and_lists_devices(
    hass: HomeAssistant,
) -> None:
    """Diagnostics redacts sensitive data and lists devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "super-secret", "refresh_token": "also-secret"},
            "products": [{"sn": "SN1", "name": "Device"}],
        },
        options={"devices": ["SN1"]},
    )
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SOC",
                "fnName": "Battery",
                "fnValue": "80",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
            # No sensorInfo at all - some SENSOR-type states never carry one.
            {"fnCode": "Weird", "fnName": "Weird", "fnValue": "1", "fnType": "SENSOR"},
        ],
    )
    coordinator = MagicMock(last_update_success=True, update_interval="0:00:30")
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry_data"]["token"] == "**REDACTED**"
    assert diagnostics["entry_data"]["products"] == "**REDACTED**"
    assert diagnostics["entry_options"] == {"devices": ["device_1"]}

    # The real serial number (device_id) must not appear anywhere in the
    # dump - it's aliased to a stable "device_N" instead.
    assert diagnostics["devices"] == [
        {
            "device_id": "device_1",
            "model": "AC200L",
            "online": True,
            "states": [
                {
                    "fn_code": "SOC",
                    "fn_type": "SENSOR",
                    "fn_value": "80",
                    "sensor_info": {
                        "sensorType": "SensorDeviceClass.BATTERY",
                        "unit": None,
                    },
                },
                {
                    "fn_code": "Weird",
                    "fn_type": "SENSOR",
                    "fn_value": "1",
                    "sensor_info": None,
                },
            ],
        }
    ]

    assert diagnostics["coordinators"]["device_1"]["last_update_success"] is True
    assert "SN1" not in diagnostics["coordinators"]


async def test_diagnostics_redacts_serial_number_used_as_a_modbus_options_key(
    hass: HomeAssistant,
) -> None:
    """Diagnostics redacts serial number used as a modbus options key.

    Regression test: entry_options["modbus"] is keyed by the same real
    serial number as entry_options["devices"] - redacting one but not the
    other would still leak it.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {},
            "products": [{"sn": "SN1", "name": "Device"}],
        },
        options={
            "devices": ["SN1"],
            "modbus": {"SN1": {"host": "10.2.1.60", "port": 502}},
        },
    )
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260"
    )
    coordinator = MagicMock(last_update_success=True, update_interval="0:00:30")
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry_options"]["modbus"] == {
        "device_1": {"host": "**REDACTED**", "port": 502}
    }
    assert "SN1" not in str(diagnostics)
    assert "10.2.1.60" not in str(diagnostics)


async def test_diagnostics_aliases_are_stable_and_correlate_across_multiple_devices(
    hass: HomeAssistant,
) -> None:
    """Diagnostics aliases are stable and correlate across multiple devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": {}, "products": []},
        options={"devices": ["SN1", "SN2"]},
    )
    entry.add_to_hass(hass)

    device1 = BluettiDevice(
        device_id="SN1", on_line="1", name="First", sn="SN1", model="AC200L"
    )
    device2 = BluettiDevice(
        device_id="SN2", on_line="0", name="Second", sn="SN2", model="EL400"
    )
    coordinator1 = MagicMock(last_update_success=True, update_interval="0:00:30")
    coordinator2 = MagicMock(last_update_success=False, update_interval="0:00:30")
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device1, device2]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator1, "SN2": coordinator2},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Two distinct devices must get two distinct, stable aliases - not both
    # collapsed to the same placeholder - so each device's states can still
    # be matched to its own coordinator entry in the same dump.
    device_ids = [d["device_id"] for d in diagnostics["devices"]]
    assert device_ids == ["device_1", "device_2"]
    assert set(diagnostics["coordinators"].keys()) == {"device_1", "device_2"}
    assert diagnostics["coordinators"]["device_1"]["last_update_success"] is True
    assert diagnostics["coordinators"]["device_2"]["last_update_success"] is False
    assert "SN1" not in str(diagnostics)
    assert "SN2" not in str(diagnostics)


async def test_diagnostics_aliases_a_device_absent_from_runtime_data(
    hass: HomeAssistant,
) -> None:
    """Diagnostics aliases a device absent from runtime data.

    Regression test: a device can be enabled in entry.options (and have a
    local Modbus connection configured) while missing from runtime_data's
    live device list (e.g. its product data went stale between an account
    rebind and the next reload). The alias map must still be built to cover
    it, or entry_options would fall back to leaking its real serial.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": {}, "products": []},
        options={
            "devices": ["SN1", "SN_STALE"],
            "modbus": {"SN_STALE": {"host": "10.2.1.61", "port": 502}},
        },
    )
    entry.add_to_hass(hass)

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="First", sn="SN1", model="AC200L"
    )
    coordinator = MagicMock(last_update_success=True, update_interval="0:00:30")
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=MagicMock(devices=[device]),
        stomp_client=MagicMock(),
        coordinators={"SN1": coordinator},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert "SN_STALE" not in str(diagnostics)
    assert set(diagnostics["entry_options"]["devices"]) == {"device_1", "device_2"}
    assert set(diagnostics["entry_options"]["modbus"].keys()) == {"device_2"}
