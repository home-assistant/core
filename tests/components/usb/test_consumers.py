"""Tests for serial port consumer attribution."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.usb import DOMAIN
from homeassistant.components.usb.models import SerialDevice, USBDevice
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER, ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import patch_scanned_serial_ports

from tests.common import MockConfigEntry, MockModule, MockUser, mock_integration
from tests.typing import WebSocketGenerator

TTY_USB0 = "/dev/ttyUSB0"
TTY_USB0_BY_ID = "/dev/serial/by-id/usb-Silicon_Labs_CP2102-if00-port0"
TTY_USB1 = "/dev/ttyUSB1"
ESPHOME_PORT = "esphome-hass://01JZ/uart0"

USB0_PORT = USBDevice(
    device=TTY_USB0,
    vid="10C4",
    pid="EA60",
    serial_number="001234",
    manufacturer="Silicon Labs",
    description="CP2102 USB to UART",
)


@pytest.fixture(name="setup_ports")
async def setup_ports_fixture(
    hass: HomeAssistant, force_usb_polling_watcher: None
) -> AsyncGenerator[None]:
    """Set up the USB integration with a local and a remote serial port."""
    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch_scanned_serial_ports(
            return_value=[
                USB0_PORT,
                SerialDevice(
                    device=ESPHOME_PORT,
                    serial_number="01JZ-uart0",
                    manufacturer="ESPHome",
                    description="Serial proxy",
                ),
            ]
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {"usb": {}})
        await hass.async_block_till_done()
        yield


async def _async_get_serial_ports(
    hass_ws_client: WebSocketGenerator, hass: HomeAssistant
) -> list[dict[str, Any]]:
    """Return the result of the `usb/serial_ports` command."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({"id": 1, "type": "usb/serial_ports"})
    response = await ws_client.receive_json()

    assert response["success"]
    return response["result"]


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    ("data", "options"),
    [
        pytest.param({"device": TTY_USB0}, {}, id="device"),
        pytest.param({"device": {"path": TTY_USB0}}, {}, id="nested_device_path"),
        pytest.param({"port": TTY_USB0}, {}, id="port"),
        pytest.param({"usb_path": TTY_USB0}, {}, id="usb_path"),
        pytest.param({}, {"usb_path": TTY_USB0}, id="usb_path_in_options"),
        pytest.param({"serial_port": TTY_USB0}, {}, id="serial_port"),
        pytest.param({"device": f"serial://{TTY_USB0}"}, {}, id="serial_url"),
        pytest.param({"device": TTY_USB0_BY_ID}, {}, id="by_id_symlink"),
        pytest.param({"device": TTY_USB0}, {"device": TTY_USB0}, id="data_and_options"),
    ],
)
async def test_config_entry_consumers(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    data: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test detecting serial ports configured in config entries."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    MockConfigEntry(
        domain="test_usb", title="Test USB", data=data, options=options
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.usb.consumers.os.path.realpath",
        side_effect=lambda path: TTY_USB0 if path == TTY_USB0_BY_ID else path,
    ):
        ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], port["consumers"]) for port in ports] == [
        (
            TTY_USB0,
            [
                {
                    "kind": "config_entry",
                    "title": "Test USB",
                    "active": False,
                    "domain": "test_usb",
                    "config_entry_id": ports[0]["consumers"][0]["config_entry_id"],
                    "slug": None,
                }
            ],
        ),
        (ESPHOME_PORT, []),
    ]


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"port": 8080}, id="tcp_port"),
        pytest.param({"port": "192.0.2.1:1234"}, id="host_and_port"),
        pytest.param({"device": {"other": TTY_USB0}}, id="unknown_nested_key"),
        pytest.param({"other": TTY_USB0}, id="unknown_key"),
        pytest.param({"device": "socket://192.0.2.1:1234"}, id="socket_url"),
    ],
)
async def test_config_entry_non_serial_values(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    data: dict[str, Any],
) -> None:
    """Test values that do not refer to a serial port are ignored."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    MockConfigEntry(domain="test_usb", title="Test USB", data=data).add_to_hass(hass)

    ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [port["consumers"] for port in ports] == [[], []]


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    ("source", "disabled_by", "num_consumers"),
    [
        pytest.param(SOURCE_IGNORE, None, 0, id="ignored_entry_hidden"),
        pytest.param(
            SOURCE_USER, ConfigEntryDisabler.USER, 1, id="disabled_entry_shown"
        ),
    ],
)
async def test_config_entry_ignored_and_disabled(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    source: str,
    disabled_by: ConfigEntryDisabler | None,
    num_consumers: int,
) -> None:
    """Test ignored entries are hidden while disabled entries are shown."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    MockConfigEntry(
        domain="test_usb",
        title="Test USB",
        data={"device": TTY_USB0},
        source=source,
        disabled_by=disabled_by,
    ).add_to_hass(hass)

    ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [len(port["consumers"]) for port in ports] == [num_consumers, 0]


@pytest.mark.usefixtures("setup_ports")
async def test_config_entry_without_usb_dependency(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test config entries of integrations not depending on `usb` are ignored."""
    mock_integration(hass, MockModule("test_no_usb"))
    MockConfigEntry(
        domain="test_no_usb", title="Test", data={"device": TTY_USB0}
    ).add_to_hass(hass)

    ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [port["consumers"] for port in ports] == [[], []]


@pytest.mark.usefixtures("setup_ports")
async def test_config_entry_after_dependency(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test config entries of integrations depending on `usb` after setup."""
    mock_integration(
        hass,
        MockModule("test_after_usb", partial_manifest={"after_dependencies": ["usb"]}),
    )
    MockConfigEntry(
        domain="test_after_usb", title="Test", data={"device": TTY_USB0}
    ).add_to_hass(hass)

    ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [len(port["consumers"]) for port in ports] == [1, 0]


@pytest.mark.usefixtures("setup_ports")
async def test_remote_port_consumer(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a config entry using a remote serial port."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    MockConfigEntry(
        domain="test_usb", title="Test USB", data={"device": ESPHOME_PORT}
    ).add_to_hass(hass)

    ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], len(port["consumers"])) for port in ports] == [
        (TTY_USB0, 0),
        (ESPHOME_PORT, 1),
    ]


@pytest.mark.usefixtures("setup_ports")
async def test_absent_configured_port(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a configured port that is not currently present."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    MockConfigEntry(
        domain="test_usb", title="Test USB", data={"device": TTY_USB1}
    ).add_to_hass(hass)

    ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert ports[-1] == {
        "device": TTY_USB1,
        "serial_number": None,
        "manufacturer": None,
        "description": None,
        "interface_description": None,
        "interface_num": None,
        "present": False,
        "matching_integrations": [],
        "consumers": [
            {
                "kind": "config_entry",
                "title": "Test USB",
                "active": False,
                "domain": "test_usb",
                "config_entry_id": ports[-1]["consumers"][0]["config_entry_id"],
                "slug": None,
            }
        ],
    }


@pytest.mark.usefixtures("setup_ports")
async def test_app_consumers(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test detecting serial ports mapped into apps."""
    apps_info = {
        "core_zwave_js": {
            "name": "Z-Wave JS",
            "state": "started",
            "devices": [TTY_USB0_BY_ID, "/dev/dri/card0"],
        },
        "some_app": {
            "name": "Some App",
            "state": "stopped",
            "devices": [TTY_USB1],
        },
        "uninstalled_app": None,
    }

    with (
        patch("homeassistant.components.usb.consumers.is_hassio", return_value=True),
        patch(
            "homeassistant.components.usb.consumers.get_addons_info",
            return_value=apps_info,
        ),
        patch(
            "homeassistant.components.usb.consumers.os.path.realpath",
            side_effect=lambda path: TTY_USB0 if path == TTY_USB0_BY_ID else path,
        ),
    ):
        ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], port["consumers"]) for port in ports] == [
        (
            TTY_USB0,
            [
                {
                    "kind": "app",
                    "title": "Z-Wave JS",
                    "active": True,
                    "domain": None,
                    "config_entry_id": None,
                    "slug": "core_zwave_js",
                }
            ],
        ),
        (ESPHOME_PORT, []),
    ]


@pytest.mark.usefixtures("setup_ports")
async def test_app_consumers_without_supervisor(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test apps are not considered without a supervisor."""
    with patch(
        "homeassistant.components.usb.consumers.get_addons_info"
    ) as mock_apps_info:
        ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert len(mock_apps_info.mock_calls) == 0
    assert [port["consumers"] for port in ports] == [[], []]


@pytest.mark.usefixtures("setup_ports")
async def test_multiple_consumers(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a port used by both an integration and an app."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    entry = MockConfigEntry(
        domain="test_usb", title="Test USB", data={"device": TTY_USB0}
    )
    entry.add_to_hass(hass)

    apps_info = {
        "some_app": {"name": "Some App", "state": "started", "devices": [TTY_USB0]}
    }

    with (
        patch("homeassistant.components.usb.consumers.is_hassio", return_value=True),
        patch(
            "homeassistant.components.usb.consumers.get_addons_info",
            return_value=apps_info,
        ),
    ):
        ports = await _async_get_serial_ports(hass_ws_client, hass)

    assert [
        (consumer["kind"], consumer["title"]) for consumer in ports[0]["consumers"]
    ] == [("config_entry", "Test USB"), ("app", "Some App")]


@pytest.mark.usefixtures("setup_ports")
async def test_serial_ports_require_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test that listing serial ports with consumers requires admin."""
    hass_admin_user.groups = []

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({"id": 1, "type": "usb/serial_ports"})
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
