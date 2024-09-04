"""Fixtures for binary_sensor entity component tests."""

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from .common import MockBinarySensor


@pytest.fixture
def mock_binary_sensor_entities() -> dict[str, MockBinarySensor]:
    """Return mock binary sensors."""
    return {
        device_class: MockBinarySensor(
            name=f"{device_class} sensor",
            is_on=True,
            unique_id=f"unique_{device_class}",
            device_class=device_class,
        )
        for device_class in BinarySensorDeviceClass
    }
