"""Test the Škoda entity base class."""

from types import SimpleNamespace
from typing import cast

from homeassistant.components.skoda.coordinator import SkodaUpdateCoordinator
from homeassistant.components.skoda.sensor import (
    SENSOR_TYPES,
    SkodaSensor,
    SkodaSensorEntityDescription,
)

VIN = "TMBJM7NP2M1TMP511"


def _description(key: str) -> SkodaSensorEntityDescription:
    """Look up a sensor's entity description by key."""
    return next(description for description in SENSOR_TYPES if description.key == key)


def _make_empty_coordinator() -> SkodaUpdateCoordinator:
    """Build a fake coordinator with no data yet, as before the first refresh."""
    return cast(SkodaUpdateCoordinator, SimpleNamespace(vin=VIN, data=None))


def test_open_api_properties_return_none_without_coordinator_data() -> None:
    """All open_api_* helper properties must return None before the coordinator has data."""
    coordinator = _make_empty_coordinator()
    entity = SkodaSensor(coordinator, _description("mileage"))

    assert entity.open_api_vehicle is None
    assert entity.open_api_odometer is None
    assert entity.open_api_air_conditioning is None
    assert entity.open_api_vehicle_status is None
    assert entity.open_api_parking_position is None
    assert entity.open_api_driving_range is None
    assert entity.open_api_charging is None
    assert entity.open_api_auxiliary_heating is None
    assert entity.open_api_active_ventilation is None


def test_device_info_falls_back_to_generic_name_without_coordinator_data() -> None:
    """The device name falls back to a generic label when no vehicle data is available yet."""
    coordinator = _make_empty_coordinator()
    entity = SkodaSensor(coordinator, _description("mileage"))

    assert entity.device_info is not None
    assert entity.device_info["name"] == "Škoda Vehicle"


def test_open_api_properties_expose_data_not_yet_used_by_any_sensor() -> None:
    """Parking position and active ventilation are exposed for future platforms."""
    vehicle = SimpleNamespace(
        parking_position="parked-somewhere",
        active_ventilation="ventilating",
        name=None,
    )
    vehicle_response = SimpleNamespace(vehicle=vehicle)
    data = SimpleNamespace(vehicle_response=vehicle_response)
    coordinator = cast(SkodaUpdateCoordinator, SimpleNamespace(vin=VIN, data=data))
    entity = SkodaSensor(coordinator, _description("mileage"))

    assert entity.open_api_parking_position == "parked-somewhere"
    assert entity.open_api_active_ventilation == "ventilating"
