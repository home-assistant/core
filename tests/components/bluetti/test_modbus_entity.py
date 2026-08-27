"""Tests for BluettiModbusEntity."""

from unittest.mock import MagicMock

from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.entity import BluettiModbusEntity
from homeassistant.components.bluetti.models import BluettiDevice


def _device() -> BluettiDevice:
    return BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260"
    )


def test_available_false_when_coordinator_update_failed() -> None:
    """Available false when coordinator update failed."""
    coordinator = MagicMock(last_update_success=False, data={"b_soc": MagicMock()})
    entity = BluettiModbusEntity(_device(), coordinator, "b_soc")

    assert entity.available is False


def test_available_false_when_field_missing_from_coordinator_data() -> None:
    """Available false when field missing from coordinator data."""
    coordinator = MagicMock(last_update_success=True, data={})
    entity = BluettiModbusEntity(_device(), coordinator, "b_soc")

    assert entity.available is False


def test_available_true_when_field_present() -> None:
    """Available true when field present."""
    coordinator = MagicMock(last_update_success=True, data={"b_soc": MagicMock()})
    entity = BluettiModbusEntity(_device(), coordinator, "b_soc")

    assert entity.available is True


def test_device_info_uses_the_same_identifier_as_the_device() -> None:
    """Device info uses the same identifier as the device."""
    coordinator = MagicMock(last_update_success=True, data={})
    entity = BluettiModbusEntity(_device(), coordinator, "b_soc")

    assert entity.device_info["identifiers"] == {(DOMAIN, "SN1")}
