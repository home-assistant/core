"""Tests for the aerosmart sensor platform."""

from homeassistant.components.aerosmart.sensor import SENSOR_DESCRIPTIONS
from homeassistant.components.sensor import SensorDeviceClass


def test_volume_device_classes() -> None:
    """Volume and flow entities expose their matching device classes."""
    expected = {
        "coarse_dust_filter_grobstaubfilter_max_foerdervolume": (
            SensorDeviceClass.VOLUME
        ),
        "ventilation_befoerderte_kubikmeter": SensorDeviceClass.VOLUME,
        "ventilation_befoerderte_luftmenge_seit_filterwechsel": (
            SensorDeviceClass.VOLUME
        ),
        "ventilation_soll_volumenstrom_abluft": (SensorDeviceClass.VOLUME_FLOW_RATE),
        "ventilation_soll_volumenstrom_zuluft": (SensorDeviceClass.VOLUME_FLOW_RATE),
    }

    assert {
        description.key: description.device_class
        for description in SENSOR_DESCRIPTIONS
        if description.key in expected
    } == expected
