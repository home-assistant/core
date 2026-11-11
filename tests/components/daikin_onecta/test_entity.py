"""Tests for the Daikin Onecta base entity."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.entity import DaikinOnectaEntity
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC


@pytest.mark.parametrize(
    ("mac_address", "embedded_id", "management_point", "expected"),
    [
        (None, None, None, {}),
        (
            "00:11:22:33:44:55",
            None,
            None,
            {"connections": {(CONNECTION_NETWORK_MAC, "00:11:22:33:44:55")}},
        ),
        (
            None,
            "gateway",
            None,
            {},
        ),
        (
            "00:11:22:33:44:55",
            "gateway",
            SimpleNamespace(model="Model", serial="Serial", version="Version"),
            {
                "connections": {(CONNECTION_NETWORK_MAC, "00:11:22:33:44:55")},
                "model": "Model",
                "serial_number": "Serial",
                "sw_version": "Version",
            },
        ),
        (
            None,
            "gateway",
            SimpleNamespace(model=None, serial=None, version=None),
            {},
        ),
    ],
)
def test_device_info(
    mac_address: str | None,
    embedded_id: str | None,
    management_point: SimpleNamespace | None,
    expected: dict[str, object],
) -> None:
    """Build device registry metadata only from available gateway data."""
    entity = object.__new__(DaikinOnectaEntity)
    device = MagicMock()
    device.id = "gateway-id"
    device.name = "Gateway name"
    device.device = SimpleNamespace(
        mac_address=mac_address,
        device_model="Gateway model",
        gateway_embedded_id=embedded_id,
    )
    device.device.management_point = MagicMock(return_value=management_point)
    entity._device = device

    device_info = entity.device_info

    assert device_info["identifiers"] == {(DOMAIN, "gateway-id")}
    assert device_info["manufacturer"] == "Daikin"
    assert device_info["model_id"] == "Gateway model"
    assert device_info["name"] == "Gateway name"
    for key, value in expected.items():
        assert device_info[key] == value
    for key in {"model", "serial_number", "sw_version"} - expected.keys():
        assert key not in device_info
    if embedded_id is None:
        device.device.management_point.assert_not_called()
    else:
        device.device.management_point.assert_called_once_with(embedded_id)
