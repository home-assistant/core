"""Test the Tesla Fleet models."""

from unittest.mock import Mock

from homeassistant.components.tesla_fleet.models import TeslaFleetVehicleData


def test_wakelock_is_per_instance() -> None:
    """Each vehicle must get its own wakelock, not a lock shared across the account."""
    kwargs = {
        "api": Mock(),
        "coordinator": Mock(),
        "vin": "VIN",
        "device": Mock(),
        "signing": False,
    }
    a = TeslaFleetVehicleData(**kwargs)
    b = TeslaFleetVehicleData(**kwargs)

    assert a.wakelock is not b.wakelock
