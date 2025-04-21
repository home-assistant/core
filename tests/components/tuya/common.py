"""Shared helpers for Tuya tests.

Pure Python code, no pyTest magic stuff here.
"""

from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tuya_sharing.device import CustomerDevice
from tuyaha.devices import climate, light, switch

from homeassistant.components.tuya.const import DPType

# Tuya API constants
DEVICE_SPECS_DIR = Path(__file__).parent / "device_specs"


def load_device_spec(name: str) -> dict[str, Any]:
    """Load a JSON device fixture from the device_specs directory.

    Automatically appends '.json' to the filename if not present.
    Converts ISO 8601 timestamps to Unix epoch seconds, as required
    by the Tuya API and the CustomerDevice constructor.
    """
    fn = name if name.endswith(".json") else f"{name}.json"
    fixture_path = DEVICE_SPECS_DIR.joinpath(fn)
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Convert timestamp fields from ISO 8601 to Unix epoch format
    for key in ("active_time", "create_time", "update_time"):
        if key in raw:
            dt = datetime.fromisoformat(raw[key]).astimezone(UTC)
            raw[key] = int(dt.timestamp())

    return raw


def make_customer_device(device_spec_name: str) -> CustomerDevice:
    """Construct a CustomerDevice instance from a device spec fixture.

    These device specs may come from Home Assistant diagnostic exports
    or the Tuya IoT API.
    """
    raw = load_device_spec(device_spec_name)

    init_kwargs = {k: v for k, v in raw.items() if k in CustomerDevice.__annotations__}
    device = CustomerDevice(**init_kwargs)

    for attr in ("function", "status_range"):  # need to parse these.
        raw_map = raw[attr]
        wrapped: dict[str, SimpleNamespace] = {}
        for code, entry in raw_map.items():
            dp_type = DPType(entry["type"])
            json_str = json.dumps(entry["value"])
            wrapped[code] = SimpleNamespace(
                type=dp_type,
                range=entry["value"].get("range"),
                values=json_str,
            )
        setattr(device, attr, wrapped)

    device.status = raw["status"]
    return device


CLIMATE_ID = "1"
CLIMATE_DATA = {
    "data": {"state": "true", "temp_unit": climate.UNIT_CELSIUS},
    "id": CLIMATE_ID,
    "ha_type": "climate",
    "name": "TestClimate",
    "dev_type": "climate",
}

LIGHT_ID = "2"
LIGHT_DATA = {
    "data": {"state": "true"},
    "id": LIGHT_ID,
    "ha_type": "light",
    "name": "TestLight",
    "dev_type": "light",
}

SWITCH_ID = "3"
SWITCH_DATA = {
    "data": {"state": True},
    "id": SWITCH_ID,
    "ha_type": "switch",
    "name": "TestSwitch",
    "dev_type": "switch",
}

LIGHT_ID_FAKE1 = "9998"
LIGHT_DATA_FAKE1 = {
    "data": {"state": "true"},
    "id": LIGHT_ID_FAKE1,
    "ha_type": "light",
    "name": "TestLightFake1",
    "dev_type": "light",
}

LIGHT_ID_FAKE2 = "9999"
LIGHT_DATA_FAKE2 = {
    "data": {"state": "true"},
    "id": LIGHT_ID_FAKE2,
    "ha_type": "light",
    "name": "TestLightFake2",
    "dev_type": "light",
}

TUYA_DEVICES = [
    climate.TuyaClimate(CLIMATE_DATA, None),
    light.TuyaLight(LIGHT_DATA, None),
    switch.TuyaSwitch(SWITCH_DATA, None),
    light.TuyaLight(LIGHT_DATA_FAKE1, None),
    light.TuyaLight(LIGHT_DATA_FAKE2, None),
]


class MockTuya:
    """Mock for Tuya devices."""

    def get_all_devices(self):
        """Return all configured devices."""
        return TUYA_DEVICES

    def get_device_by_id(self, dev_id):
        """Return configured device with dev id."""
        if dev_id == LIGHT_ID_FAKE1:
            return None
        if dev_id == LIGHT_ID_FAKE2:
            return switch.TuyaSwitch(SWITCH_DATA, None)
        for device in TUYA_DEVICES:
            if device.object_id() == dev_id:
                return device
        return None
