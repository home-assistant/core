"""Tests for switch helpers."""

from homeassistant.components.switch import DOMAIN, SwitchDeviceClass
from homeassistant.components.switch.helpers import (
    create_switch_device_class_select_selector,
)


def test_create_switch_device_class_select_selector() -> None:
    "Test Create sensor state class select selector helper."
    selector = create_switch_device_class_select_selector()
    assert selector.config["options"] == list(SwitchDeviceClass)
    assert selector.config["translation_domain"] == DOMAIN
    assert selector.config["translation_key"] == "device_class"
    assert selector.config["sort"]
    assert not selector.config["custom_value"]
