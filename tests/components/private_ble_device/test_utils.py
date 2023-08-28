"""Test utils."""
from homeassistant.components.private_ble_device.utils import calculate_distance_meters


def tests_calculate_distance_meters():
    """Test distance estimate calculation."""
    assert calculate_distance_meters(-59, -60) == 1.1352362990362899
    assert calculate_distance_meters(59, -60) == 1.183020818815412
    assert calculate_distance_meters(12, -80) == 400.0
    assert calculate_distance_meters(59, 0) is None
    assert calculate_distance_meters(-3, -100) == 400.0
    assert calculate_distance_meters(-3, -96) == 400.0
    assert calculate_distance_meters(-3, -3) == 1.01076
    assert calculate_distance_meters(-4, -3) == 0.056313514709472656
