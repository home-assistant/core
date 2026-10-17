"""Tests for serial port consumer attribution."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.hassio import HassioNotReadyError
from homeassistant.components.usb import DOMAIN
from homeassistant.components.usb.models import SerialDevice, USBDevice
from homeassistant.components.usb.utils import usb_service_info_from_device
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USB,
    SOURCE_USER,
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.setup import async_setup_component

from . import patch_scanned_serial_ports

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
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
    """Return the result of the `usb/list_serial_ports` command with usage."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {"id": 1, "type": "usb/list_serial_ports", "include_usage": True}
    )
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
    entry = MockConfigEntry(
        domain="test_usb", title="Test USB", data=data, options=options
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.usb.consumers.os.path.realpath",
        side_effect=lambda path: TTY_USB0 if path == TTY_USB0_BY_ID else path,
    ):
        result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], port["consumers"]) for port in result] == [
        (
            TTY_USB0,
            [
                {
                    "kind": "config_entry",
                    "title": "Test USB",
                    "active": False,
                    "domain": "test_usb",
                    "config_entry_id": entry.entry_id,
                    "slug": None,
                }
            ],
        ),
        (ESPHOME_PORT, []),
    ]


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    "device",
    [
        pytest.param(f"serial://{TTY_USB0}", id="serial_url"),
        pytest.param(f"serial://{TTY_USB0}:4800", id="serial_url_with_baud"),
        pytest.param(f"device://{TTY_USB0}:4800", id="device_url_with_baud"),
        pytest.param(f"{TTY_USB0}:4800", id="bare_path_with_baud"),
    ],
)
async def test_config_entry_upb_url(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device: str,
) -> None:
    """Test upb's URL forms with an optional baud rate suffix."""
    mock_integration(hass, MockModule("upb", dependencies=["usb"]))
    MockConfigEntry(domain="upb", title="UPB", data={"device": device}).add_to_hass(
        hass
    )

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], len(port["consumers"])) for port in result] == [
        (TTY_USB0, 1),
        (ESPHOME_PORT, 0),
    ]


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    ("state", "active"),
    [
        pytest.param(ConfigEntryState.LOADED, True, id="loaded"),
        pytest.param(ConfigEntryState.SETUP_RETRY, True, id="setup_retry"),
        pytest.param(ConfigEntryState.SETUP_IN_PROGRESS, True, id="setup_in_progress"),
        pytest.param(
            ConfigEntryState.UNLOAD_IN_PROGRESS, True, id="unload_in_progress"
        ),
        pytest.param(ConfigEntryState.FAILED_UNLOAD, True, id="failed_unload"),
        pytest.param(ConfigEntryState.NOT_LOADED, False, id="not_loaded"),
        pytest.param(ConfigEntryState.SETUP_ERROR, False, id="setup_error"),
        pytest.param(ConfigEntryState.MIGRATION_ERROR, False, id="migration_error"),
    ],
)
async def test_config_entry_active_states(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    state: ConfigEntryState,
    active: bool,
) -> None:
    """Test which config entry states mark the consumer as active."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    MockConfigEntry(
        domain="test_usb", title="Test USB", data={"device": TTY_USB0}, state=state
    ).add_to_hass(hass)

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [consumer["active"] for consumer in result[0]["consumers"]] == [active]


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"port": 8080}, id="tcp_port"),
        pytest.param({"port": "192.0.2.1:1234"}, id="host_and_port"),
        pytest.param({"device": {"other": TTY_USB0}}, id="unknown_nested_key"),
        pytest.param({"other": TTY_USB0}, id="unknown_key"),
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

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [port["consumers"] for port in result] == [[], []]


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

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [len(port["consumers"]) for port in result] == [num_consumers, 0]


@pytest.mark.usefixtures("setup_ports")
async def test_socket_path_psk_not_exposed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the noise PSK in zwave_js's esphome socket path is stripped."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    MockConfigEntry(
        domain="test_usb",
        title="Test USB",
        data={"socket_path": "esphome://192.0.2.5:6053/?key=secret-psk"},
    ).add_to_hass(hass)

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [
        (port["device"], port["present"], len(port["consumers"])) for port in result
    ] == [
        (TTY_USB0, True, 0),
        (ESPHOME_PORT, True, 0),
        ("esphome://192.0.2.5:6053/", True, 1),
    ]
    assert "secret-psk" not in str(result)


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    ("domain", "data"),
    [
        pytest.param("alarmdecoder", {"device_path": TTY_USB0}, id="alarmdecoder"),
        pytest.param("bryant_evolution", {"filename": TTY_USB0}, id="bryant_evolution"),
        pytest.param("elkm1", {"host": f"serial://{TTY_USB0}:115200"}, id="elkm1"),
        pytest.param("mysensors", {"device": TTY_USB0}, id="mysensors"),
    ],
)
async def test_non_usb_serial_domains(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    domain: str,
    data: dict[str, Any],
) -> None:
    """Test integrations holding a serial port without a `usb` dependency."""
    mock_integration(hass, MockModule(domain))
    MockConfigEntry(domain=domain, title="Test", data=data).add_to_hass(hass)

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [len(port["consumers"]) for port in result] == [1, 0]


@pytest.mark.usefixtures("setup_ports")
async def test_config_entry_unknown_integration(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test config entries of integrations that fail to resolve are ignored."""
    MockConfigEntry(
        domain="removed_custom_component", title="Test", data={"device": TTY_USB0}
    ).add_to_hass(hass)

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [port["consumers"] for port in result] == [[], []]


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

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [port["consumers"] for port in result] == [[], []]


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

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [len(port["consumers"]) for port in result] == [1, 0]


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

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], len(port["consumers"])) for port in result] == [
        (TTY_USB0, 0),
        (ESPHOME_PORT, 1),
    ]


@pytest.mark.usefixtures("setup_ports")
@pytest.mark.parametrize(
    ("device", "present"),
    [
        pytest.param(TTY_USB1, False, id="local"),
        pytest.param("esphome-hass://02AB/uart0", False, id="esphome_proxy"),
        pytest.param("esphome://ttl-to-serial.local/uart1", True, id="esphome"),
        pytest.param("socket://192.0.2.1:1234", True, id="socket"),
        pytest.param("tcp://192.0.2.1:1234", True, id="tcp"),
        pytest.param("rfc2217://192.0.2.1:1234", True, id="rfc2217"),
    ],
)
async def test_configured_port_not_scanned(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device: str,
    present: bool,
) -> None:
    """Test a configured port that is not in the scan.

    Scannable ports are absent, unscannable URLs are assumed present.
    """
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    entry = MockConfigEntry(
        domain="test_usb", title="Test USB", data={"device": device}
    )
    entry.add_to_hass(hass)

    result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], port["present"]) for port in result] == [
        (TTY_USB0, True),
        (ESPHOME_PORT, True),
        (device, present),
    ]
    assert result[2] == {
        "device": device,
        "resolved_device": None,
        "serial_number": None,
        "manufacturer": None,
        "description": None,
        "interface_description": None,
        "interface_num": None,
        "matching_integrations": [],
        "present": present,
        "discovery_flows": [],
        "consumers": [
            {
                "kind": "config_entry",
                "title": "Test USB",
                "active": False,
                "domain": "test_usb",
                "config_entry_id": entry.entry_id,
                "slug": None,
            }
        ],
    }


@pytest.mark.usefixtures("setup_ports")
async def test_app_consumers(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test detecting serial ports configured in the options of apps."""
    apps_info = {
        "core_zwave_js": {
            "name": "Z-Wave JS",
            "state": "started",
            "devices": [TTY_USB0],
            "options": {"device": TTY_USB0_BY_ID, "gpu": "/dev/dri/card0"},
        },
        "some_app": {
            "name": "Some App",
            "state": "stopped",
            "devices": [TTY_USB1],
            "options": {"serial": [{"port": TTY_USB0}]},
        },
        # Static devices of the manifest are mapped regardless of being used
        "wmbusmeters": {
            "name": "Wmbusmeters",
            "state": "started",
            "devices": [TTY_USB0, TTY_USB1],
            "options": {"reset_config": False},
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
        result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], port["consumers"]) for port in result] == [
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
                },
                {
                    "kind": "app",
                    "title": "Some App",
                    "active": False,
                    "domain": None,
                    "config_entry_id": None,
                    "slug": "some_app",
                },
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
        result = await _async_get_serial_ports(hass_ws_client, hass)

    assert len(mock_apps_info.mock_calls) == 0
    assert [port["consumers"] for port in result] == [[], []]


@pytest.mark.usefixtures("setup_ports")
async def test_app_consumers_supervisor_not_ready(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test apps are not considered when the supervisor is not ready yet."""
    with (
        patch("homeassistant.components.usb.consumers.is_hassio", return_value=True),
        patch(
            "homeassistant.components.usb.consumers.get_addons_info",
            side_effect=HassioNotReadyError("Not ready"),
        ),
    ):
        result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [port["consumers"] for port in result] == [[], []]


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
        "some_app": {
            "name": "Some App",
            "state": "started",
            "devices": [TTY_USB0],
            "options": {"device": TTY_USB0},
        }
    }

    with (
        patch("homeassistant.components.usb.consumers.is_hassio", return_value=True),
        patch(
            "homeassistant.components.usb.consumers.get_addons_info",
            return_value=apps_info,
        ),
    ):
        result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [
        (consumer["kind"], consumer["title"]) for consumer in result[0]["consumers"]
    ] == [("config_entry", "Test USB"), ("app", "Some App")]


class MockUsbFlow(ConfigFlow):
    """Config flow that keeps USB discoveries in progress."""

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Show a form so the discovery flow stays in progress."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show a form so the discovery flow stays in progress."""
        return self.async_show_form(step_id="confirm")


@pytest.mark.usefixtures("setup_ports")
async def test_discovery_flows(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that in-progress discovery flows are listed for their serial port."""
    mock_integration(hass, MockModule("test_usb", dependencies=["usb"]))
    mock_platform(hass, "test_usb.config_flow", None)

    with mock_config_flow("test_usb", MockUsbFlow):
        flow = await hass.config_entries.flow.async_init(
            "test_usb",
            context={"source": SOURCE_USB},
            data=usb_service_info_from_device(USB0_PORT),
        )

        result = await _async_get_serial_ports(hass_ws_client, hass)

    assert [(port["device"], port["discovery_flows"]) for port in result] == [
        (TTY_USB0, [{"flow_id": flow["flow_id"], "domain": "test_usb"}]),
        (ESPHOME_PORT, []),
    ]
