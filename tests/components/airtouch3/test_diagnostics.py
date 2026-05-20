"""Test AirTouch 3 diagnostics."""

from typing import cast

from pyairtouch3.airtouch_aircon import Aircon
from pyairtouch3.airtouch_sensor import Sensor
from pyairtouch3.airtouch_zone import AirtouchZone
from pyairtouch3.enums import AcMode, ZoneStatus

from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.coordinator import (
    Airtouch3DataUpdateCoordinator,
)
from homeassistant.components.airtouch3.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _sensor(temperature: int) -> Sensor:
    """Create an available sensor."""
    sensor = Sensor()
    sensor.current_temperature = temperature
    sensor.is_available = True
    return sensor


def _zone(
    zone_id: int,
    name: str,
    desired_temperature: int,
    status: ZoneStatus,
    sensor: Sensor | None = None,
) -> AirtouchZone:
    """Create a zone fixture."""
    zone = AirtouchZone(20)
    zone.id = zone_id
    zone.name = name
    zone.desired_temperature = desired_temperature
    zone.status = status
    if sensor:
        zone.sensor = sensor
    return zone


def _aircon() -> Aircon:
    """Create AirTouch data for diagnostics tests."""
    aircon = Aircon(1)
    aircon.brand_id = 2
    aircon.desired_temperature = 22
    aircon.fan_speed = 2
    aircon.mode = AcMode.COOL
    aircon.room_temperature = 19
    aircon.status = True
    aircon.zones = [
        _zone(1, "Living", 20, ZoneStatus.ZONE_ON, _sensor(23)),
        _zone(2, "Bedroom", 21, ZoneStatus.ZONE_OFF),
    ]
    return aircon


def _entry_with_coordinator(
    hass: HomeAssistant, data: Aircon | None
) -> MockConfigEntry:
    """Create a config entry with coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        options={},
    )
    entry.add_to_hass(hass)
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")
    coordinator.data = cast(Aircon, data)
    entry.runtime_data = coordinator
    return entry


async def test_config_entry_diagnostics_redacts_host(hass: HomeAssistant) -> None:
    """Test config entry diagnostics."""
    entry = _entry_with_coordinator(hass, _aircon())

    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "config_entry": {
            "data": {CONF_HOST: REDACTED},
            "options": {},
        },
        "airtouch3": {
            "ac_id": 1,
            "brand_id": 2,
            "status": True,
            "fan_speed": 2,
            "mode": "COOL",
            "room_temperature": 19,
            "desired_temperature": 22,
            "zone_count": 2,
            "zones": [
                {
                    "id": 1,
                    "name": "Living",
                    "status": "ZONE_ON",
                    "touch_pad_temperature": 20,
                    "desired_temperature": 20,
                    "sensor": {
                        "available": True,
                        "current_temperature": 23,
                    },
                },
                {
                    "id": 2,
                    "name": "Bedroom",
                    "status": "ZONE_OFF",
                    "touch_pad_temperature": 20,
                    "desired_temperature": 21,
                    "sensor": {
                        "available": False,
                        "current_temperature": None,
                    },
                },
            ],
        },
    }


async def test_config_entry_diagnostics_without_data(hass: HomeAssistant) -> None:
    """Test config entry diagnostics without coordinator data."""
    entry = _entry_with_coordinator(hass, None)

    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "config_entry": {
            "data": {CONF_HOST: REDACTED},
            "options": {},
        },
        "airtouch3": None,
    }
