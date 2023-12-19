"""Test deprecated binary sensor device classes."""
from homeassistant.components import binary_sensor


def import_deprecated(device_class: binary_sensor.BinarySensorDeviceClass):
    """Import deprecated device class constant."""
    getattr(binary_sensor, f"DEVICE_CLASS_{device_class.name}")
