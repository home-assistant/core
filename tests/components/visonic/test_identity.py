"""Test normalization of connection identities used for duplicate detection."""

import pytest

from homeassistant.components.visonic.identity import (
    connection_identity,
    resolved_connection_identity,
)
from homeassistant.components.visonic.visonic_types import DeviceType
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            {CONF_TYPE: DeviceType.ETHERNET, CONF_PORT: 30000}, id="missing-host"
        ),
        pytest.param({CONF_TYPE: DeviceType.SERIAL}, id="missing-serial-path"),
        pytest.param({CONF_TYPE: DeviceType.CLOUD}, id="missing-cloud-serial"),
        pytest.param({}, id="missing-transport"),
    ],
)
def test_incomplete_connection_has_no_identity(data: dict[str, str | int]) -> None:
    """Incomplete settings cannot reserve another panel's connection."""
    assert connection_identity(data) is None


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(
            {
                CONF_TYPE: DeviceType.ETHERNET,
                CONF_HOST: " PANEL.EXAMPLE.COM. ",
                CONF_PORT: "30000",
            },
            (DeviceType.ETHERNET, "panel.example.com", "30000"),
            id="dns-name",
        ),
        pytest.param(
            {CONF_TYPE: DeviceType.SERIAL, CONF_DEVICE: "/dev/serial/../ttyUSB0"},
            (DeviceType.SERIAL, "/dev/ttyUSB0"),
            id="serial-path",
        ),
        pytest.param(
            {
                CONF_TYPE: DeviceType.SERIAL,
                CONF_DEVICE: "esphome-hass://esphome/entry-id?port_name=uart",
            },
            (DeviceType.SERIAL, "esphome-hass://esphome/entry-id?port_name=uart"),
            id="esphome-serial-proxy",
        ),
        pytest.param(
            {CONF_TYPE: DeviceType.SERIAL, CONF_DEVICE: "socket://192.0.2.1:30000"},
            (DeviceType.SERIAL, "socket://192.0.2.1:30000"),
            id="socket-url",
        ),
    ],
)
def test_equivalent_endpoints_share_identity(
    data: dict[str, str | int], expected: tuple[str, ...]
) -> None:
    """Normalize equivalent endpoint spellings before checking for duplicates."""
    assert connection_identity(data) == expected
    assert resolved_connection_identity(data) == expected
