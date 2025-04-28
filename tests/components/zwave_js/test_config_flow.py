"""Test the Z-Wave JS config flow."""

import asyncio
from collections.abc import Generator
from copy import copy
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import AddonsOptions, Discovery
import aiohttp
import pytest
from serial.tools.list_ports_common import ListPortInfo
from zwave_js_server.exceptions import FailedCommand
from zwave_js_server.version import VersionInfo

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.zwave_js.config_flow import SERVER_VERSION_TIMEOUT, TITLE
from homeassistant.components.zwave_js.const import ADDON_SLUG, CONF_USB_PATH, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, async_capture_events

ADDON_DISCOVERY_INFO = {
    "addon": "Z-Wave JS",
    "host": "host1",
    "port": 3001,
}


USB_DISCOVERY_INFO = UsbServiceInfo(
    device="/dev/zwave",
    pid="AAAA",
    vid="AAAA",
    serial_number="1234",
    description="zwave radio",
    manufacturer="test",
)

NORTEK_ZIGBEE_DISCOVERY_INFO = UsbServiceInfo(
    device="/dev/zigbee",
    pid="8A2A",
    vid="10C4",
    serial_number="1234",
    description="nortek zigbee radio",
    manufacturer="nortek",
)

CP2652_ZIGBEE_DISCOVERY_INFO = UsbServiceInfo(
    device="/dev/zigbee",
    pid="EA60",
    vid="10C4",
    serial_number="",
    description="cp2652",
    manufacturer="generic",
)


@pytest.fixture(name="setup_entry")
def setup_entry_fixture() -> Generator[AsyncMock]:
    """Mock entry setup."""
    with patch(
        "homeassistant.components.zwave_js.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="unload_entry")
def unload_entry_fixture() -> Generator[AsyncMock]:
    """Mock entry unload."""
    with patch(
        "homeassistant.components.zwave_js.async_unload_entry", return_value=True
    ) as mock_unload_entry:
        yield mock_unload_entry


@pytest.fixture(name="supervisor")
def mock_supervisor_fixture() -> Generator[None]:
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.zwave_js.config_flow.is_hassio", return_value=True
    ):
        yield


@pytest.fixture(name="server_version_side_effect")
def server_version_side_effect_fixture() -> Any | None:
    """Return the server version side effect."""
    return None


@pytest.fixture(name="get_server_version", autouse=True)
def mock_get_server_version(
    server_version_side_effect: Any | None, server_version_timeout: int
) -> Generator[AsyncMock]:
    """Mock server version."""
    version_info = VersionInfo(
        driver_version="mock-driver-version",
        server_version="mock-server-version",
        home_id=1234,
        min_schema_version=0,
        max_schema_version=1,
    )
    with (
        patch(
            "homeassistant.components.zwave_js.config_flow.get_server_version",
            side_effect=server_version_side_effect,
            return_value=version_info,
        ) as mock_version,
        patch(
            "homeassistant.components.zwave_js.config_flow.SERVER_VERSION_TIMEOUT",
            new=server_version_timeout,
        ),
    ):
        yield mock_version


@pytest.fixture(name="server_version_timeout")
def mock_server_version_timeout() -> int:
    """Patch the timeout for getting server version."""
    return SERVER_VERSION_TIMEOUT


@pytest.fixture(name="addon_setup_time", autouse=True)
def mock_addon_setup_time() -> Generator[None]:
    """Mock add-on setup sleep time."""
    with patch(
        "homeassistant.components.zwave_js.config_flow.ADDON_SETUP_TIMEOUT", new=0
    ):
        yield


@pytest.fixture(name="serial_port")
def serial_port_fixture() -> ListPortInfo:
    """Return a mock serial port."""
    port = ListPortInfo("/test", skip_link_detection=True)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/test"
    port.description = "Some serial port"
    port.pid = 9876
    port.vid = 5678

    return port


@pytest.fixture(name="mock_list_ports", autouse=True)
def mock_list_ports_fixture(serial_port) -> Generator[MagicMock]:
    """Mock list ports."""
    with patch(
        "homeassistant.components.zwave_js.config_flow.list_ports.comports"
    ) as mock_list_ports:
        another_port = copy(serial_port)
        another_port.device = "/new"
        another_port.description = "New serial port"
        another_port.serial_number = "5678"
        another_port.pid = 8765
        no_vid_port = copy(serial_port)
        no_vid_port.device = "/no_vid"
        no_vid_port.description = "Port without vid"
        no_vid_port.serial_number = "9123"
        no_vid_port.vid = None
        mock_list_ports.return_value = [serial_port, another_port, no_vid_port]
        yield mock_list_ports


@pytest.fixture(name="mock_usb_serial_by_id", autouse=True)
def mock_usb_serial_by_id_fixture() -> Generator[MagicMock]:
    """Mock usb serial by id."""
    with patch(
        "homeassistant.components.zwave_js.config_flow.usb.get_serial_by_id"
    ) as mock_usb_serial_by_id:
        mock_usb_serial_by_id.side_effect = lambda x: x
        yield mock_usb_serial_by_id


async def test_manual(hass: HomeAssistant) -> None:
    """Test we create an entry with manual step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Z-Wave JS"
    assert result2["data"] == {
        "url": "ws://localhost:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
        "lr_s2_access_control_key": None,
        "lr_s2_authenticated_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id == "1234"


async def slow_server_version(*args):
    """Simulate a slow server version."""
    await asyncio.sleep(0.1)


@pytest.mark.parametrize(
    ("url", "server_version_side_effect", "server_version_timeout", "error"),
    [
        (
            "not-ws-url",
            None,
            SERVER_VERSION_TIMEOUT,
            "invalid_ws_url",
        ),
        (
            "ws://localhost:3000",
            slow_server_version,
            0,
            "cannot_connect",
        ),
        (
            "ws://localhost:3000",
            Exception("Boom"),
            SERVER_VERSION_TIMEOUT,
            "unknown",
        ),
    ],
)
async def test_manual_errors(hass: HomeAssistant, integration, url, error) -> None:
    """Test all errors with a manual set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": url,
        },
    )

    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("url", "server_version_side_effect", "server_version_timeout", "error"),
    [
        (
            "not-ws-url",
            None,
            SERVER_VERSION_TIMEOUT,
            "invalid_ws_url",
        ),
        (
            "ws://localhost:3000",
            slow_server_version,
            0,
            "cannot_connect",
        ),
        (
            "ws://localhost:3000",
            Exception("Boom"),
            SERVER_VERSION_TIMEOUT,
            "unknown",
        ),
    ],
)
async def test_reconfigure_manual_errors(
    hass: HomeAssistant, integration, url, error
) -> None:
    """Test all errors with a manual set up in a reconfigure flow."""
    entry = integration
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": url,
        },
    )

    assert result["step_id"] == "manual_reconfigure"
    assert result["errors"] == {"base": error}


async def test_manual_already_configured(hass: HomeAssistant) -> None:
    """Test that only one unique instance is allowed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "integration_created_addon": True,
        },
        title=TITLE,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://1.1.1.1:3001",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["url"] == "ws://1.1.1.1:3001"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_supervisor_discovery(
    hass: HomeAssistant,
    supervisor,
    addon_running,
    addon_options,
    get_addon_discovery_info,
) -> None:
    """Test flow started from Supervisor discovery."""

    addon_options["device"] = "/test"
    addon_options["s0_legacy_key"] = "new123"
    addon_options["s2_access_control_key"] = "new456"
    addon_options["s2_authenticated_key"] = "new789"
    addon_options["s2_unauthenticated_key"] = "new987"
    addon_options["lr_s2_access_control_key"] = "new654"
    addon_options["lr_s2_authenticated_key"] = "new321"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("discovery_info", "server_version_side_effect"),
    [({"config": ADDON_DISCOVERY_INFO}, TimeoutError())],
)
async def test_supervisor_discovery_cannot_connect(
    hass: HomeAssistant, supervisor, get_addon_discovery_info
) -> None:
    """Test Supervisor discovery and cannot connect."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_clean_discovery_on_user_create(
    hass: HomeAssistant,
    supervisor,
    addon_running,
    addon_options,
    get_addon_discovery_info,
) -> None:
    """Test discovery flow is cleaned up when a user flow is finished."""

    addon_options["device"] = "/test"
    addon_options["s0_legacy_key"] = "new123"
    addon_options["s2_access_control_key"] = "new456"
    addon_options["s2_authenticated_key"] = "new789"
    addon_options["s2_unauthenticated_key"] = "new987"
    addon_options["lr_s2_access_control_key"] = "new654"
    addon_options["lr_s2_authenticated_key"] = "new321"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://localhost:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
        "lr_s2_access_control_key": None,
        "lr_s2_authenticated_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_discovery_with_existing_entry(
    hass: HomeAssistant, supervisor, addon_running, addon_options
) -> None:
    """Test discovery flow is aborted if an entry already exists."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "ws://localhost:3000"},
        title=TITLE,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Assert that the entry data is updated with discovery info.
    assert entry.data["url"] == "ws://host1:3001"


async def test_abort_hassio_discovery_with_existing_flow(
    hass: HomeAssistant, supervisor, addon_installed, addon_options
) -> None:
    """Test hassio discovery flow is aborted when another discovery has happened."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


async def test_abort_hassio_discovery_for_other_addon(
    hass: HomeAssistant, supervisor, addon_installed, addon_options
) -> None:
    """Test hassio discovery flow is aborted for a non official add-on discovery."""
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config={
                "addon": "Other Z-Wave JS",
                "host": "host1",
                "port": 3001,
            },
            name="Other Z-Wave JS",
            slug="other_addon",
            uuid="1234",
        ),
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "not_zwave_js_addon"


@pytest.mark.parametrize(
    ("usb_discovery_info", "device", "discovery_name"),
    [
        (
            USB_DISCOVERY_INFO,
            USB_DISCOVERY_INFO.device,
            "zwave radio",
        ),
        (
            UsbServiceInfo(
                device="/dev/zwa2",
                pid="303A",
                vid="4001",
                serial_number="1234",
                description="ZWA-2 - Nabu Casa ZWA-2",
                manufacturer="Nabu Casa",
            ),
            "/dev/zwa2",
            "Home Assistant Connect ZWA-2",
        ),
    ],
)
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_usb_discovery(
    hass: HomeAssistant,
    supervisor,
    addon_not_installed,
    install_addon,
    addon_options,
    get_addon_discovery_info,
    set_addon_options,
    start_addon,
    usb_discovery_info: UsbServiceInfo,
    device: str,
    discovery_name: str,
) -> None:
    """Test usb discovery success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=usb_discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"
    assert result["description_placeholders"] == {"name": discovery_name}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": device,
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": device,
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_usb_discovery_addon_not_running(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
) -> None:
    """Test usb discovery when add-on is installed but not running."""
    addon_options["device"] = "/dev/incorrect_device"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    # Make sure the discovered usb device is preferred.
    data_schema = result["data_schema"]
    assert data_schema({}) == {
        "s0_legacy_key": "",
        "s2_access_control_key": "",
        "s2_authenticated_key": "",
        "s2_unauthenticated_key": "",
        "lr_s2_access_control_key": "",
        "lr_s2_authenticated_key": "",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": USB_DISCOVERY_INFO.device,
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": USB_DISCOVERY_INFO.device,
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("supervisor", "addon_running", "get_addon_discovery_info")
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_usb_discovery_migration(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    restart_addon: AsyncMock,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test usb discovery migration."""
    addon_options["device"] = "/dev/ttyUSB0"
    entry = integration
    hass.config_entries.async_update_entry(
        entry,
        unique_id="1234",
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "usb_path": "/dev/ttyUSB0",
        },
    )

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm backup progress", {"bytesRead": 100, "total": 200}
        )
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    async def mock_restore_nvm(data: bytes):
        client.driver.controller.emit(
            "nvm convert progress",
            {"event": "nvm convert progress", "bytesRead": 100, "total": 200},
        )
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm restore progress",
            {"event": "nvm restore progress", "bytesWritten": 100, "total": 200},
        )

    client.driver.controller.async_restore_nvm = AsyncMock(side_effect=mock_restore_nvm)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes", MagicMock()) as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1
        assert len(events) == 1
        assert events[0].data["progress"] == 0.5
        events.clear()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config={"device": USB_DISCOVERY_INFO.device})
    )

    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "restore_nvm"

    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert client.driver.controller.async_restore_nvm.call_count == 1
    assert len(events) == 2
    assert events[0].data["progress"] == 0.25
    assert events[1].data["progress"] == 0.75

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert integration.data["url"] == "ws://host1:3001"
    assert integration.data["usb_path"] == USB_DISCOVERY_INFO.device
    assert integration.data["use_addon"] is True


async def test_discovery_addon_not_running(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
) -> None:
    """Test discovery with add-on already installed but not running."""
    addon_options["device"] = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["step_id"] == "hassio_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_addon_not_installed(
    hass: HomeAssistant,
    supervisor,
    addon_not_installed,
    install_addon,
    addon_options,
    set_addon_options,
    start_addon,
) -> None:
    """Test discovery with add-on not installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["step_id"] == "hassio_confirm"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["step_id"] == "install_addon"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_usb_discovery_with_existing_flow(
    hass: HomeAssistant, supervisor, addon_options
) -> None:
    """Test usb discovery flow is aborted when another discovery has happened."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=ADDON_DISCOVERY_INFO,
            name="Z-Wave JS",
            slug=ADDON_SLUG,
            uuid="1234",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


async def test_abort_usb_discovery_addon_required(
    hass: HomeAssistant, supervisor, addon_options
) -> None:
    """Test usb discovery aborted when existing entry not using add-on."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "ws://localhost:3000"},
        title=TITLE,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_required"


@pytest.mark.usefixtures(
    "supervisor",
    "addon_running",
)
async def test_abort_usb_discovery_confirm_addon_required(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
) -> None:
    """Test usb discovery confirm aborted when existing entry not using add-on."""
    addon_options["device"] = "/dev/another_device"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "ws://localhost:3000",
            "usb_path": "/dev/another_device",
            "use_addon": True,
        },
        title=TITLE,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "use_addon": False,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_required"


async def test_usb_discovery_requires_supervisor(hass: HomeAssistant) -> None:
    """Test usb discovery flow is aborted when there is no supervisor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_requires_supervisor"


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_usb_discovery_same_device(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
) -> None:
    """Test usb discovery flow is aborted when the add-on device is discovered."""
    addon_options["device"] = USB_DISCOVERY_INFO.device
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "discovery_info",
    [CP2652_ZIGBEE_DISCOVERY_INFO],
)
async def test_abort_usb_discovery_aborts_specific_devices(
    hass: HomeAssistant, supervisor, addon_options, discovery_info
) -> None:
    """Test usb discovery flow is aborted on specific devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_zwave_device"


async def test_not_addon(hass: HomeAssistant, supervisor) -> None:
    """Test opting out of add-on on Supervisor."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://localhost:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
        "lr_s2_access_control_key": None,
        "lr_s2_authenticated_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_running(
    hass: HomeAssistant,
    supervisor,
    addon_running,
    addon_options,
    get_addon_discovery_info,
) -> None:
    """Test add-on already running on Supervisor."""
    addon_options["device"] = "/test"
    addon_options["s0_legacy_key"] = "new123"
    addon_options["s2_access_control_key"] = "new456"
    addon_options["s2_authenticated_key"] = "new789"
    addon_options["s2_unauthenticated_key"] = "new987"
    addon_options["lr_s2_access_control_key"] = "new654"
    addon_options["lr_s2_authenticated_key"] = "new321"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": True}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "discovery_info",
        "discovery_info_side_effect",
        "server_version_side_effect",
        "addon_info_side_effect",
        "abort_reason",
    ),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            SupervisorError(),
            None,
            None,
            "addon_get_discovery_info_failed",
        ),
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            TimeoutError,
            None,
            "cannot_connect",
        ),
        (
            [],
            None,
            None,
            None,
            "addon_get_discovery_info_failed",
        ),
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            None,
            None,
            SupervisorError(),
            "addon_info_failed",
        ),
    ],
)
async def test_addon_running_failures(
    hass: HomeAssistant,
    supervisor,
    addon_running,
    addon_options,
    get_addon_discovery_info,
    abort_reason,
) -> None:
    """Test all failures when add-on is running."""
    addon_options["device"] = "/test"
    addon_options["network_key"] = "abc123"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_running_already_configured(
    hass: HomeAssistant,
    supervisor,
    addon_running,
    addon_options,
    get_addon_discovery_info,
) -> None:
    """Test that only one unique instance is allowed when add-on is running."""
    addon_options["device"] = "/test_new"
    addon_options["s0_legacy_key"] = "new123"
    addon_options["s2_access_control_key"] = "new456"
    addon_options["s2_authenticated_key"] = "new789"
    addon_options["s2_unauthenticated_key"] = "new987"
    addon_options["lr_s2_access_control_key"] = "new654"
    addon_options["lr_s2_authenticated_key"] = "new321"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "ws://localhost:3000",
            "usb_path": "/test",
            "network_key": "old123",
            "s0_legacy_key": "old123",
            "s2_access_control_key": "old456",
            "s2_authenticated_key": "old789",
            "s2_unauthenticated_key": "old987",
            "lr_s2_access_control_key": "old654",
            "lr_s2_authenticated_key": "old321",
        },
        title=TITLE,
        unique_id=1234,  # Unique ID is purposely set to int to test migration logic
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == "/test_new"
    assert entry.data["s0_legacy_key"] == "new123"
    assert entry.data["s2_access_control_key"] == "new456"
    assert entry.data["s2_authenticated_key"] == "new789"
    assert entry.data["s2_unauthenticated_key"] == "new987"
    assert entry.data["lr_s2_access_control_key"] == "new654"
    assert entry.data["lr_s2_authenticated_key"] == "new321"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_installed(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
) -> None:
    """Test add-on already installed but not running on Supervisor."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("discovery_info", "start_addon_side_effect"),
    [
        (
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            ),
            SupervisorError(),
        )
    ],
)
async def test_addon_installed_start_failure(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
) -> None:
    """Test add-on start failure when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize(
    ("discovery_info", "server_version_side_effect"),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            TimeoutError,
        ),
        (
            [],
            None,
        ),
    ],
)
async def test_addon_installed_failures(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
) -> None:
    """Test all failures when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize(
    ("set_addon_options_side_effect", "discovery_info"),
    [
        (
            SupervisorError(),
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
        )
    ],
)
async def test_addon_installed_set_options_failure(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
) -> None:
    """Test all failures when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_set_config_failed"

    assert start_addon.call_count == 0


async def test_addon_installed_usb_ports_failure(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
) -> None:
    """Test usb ports failure when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    with patch(
        "homeassistant.components.zwave_js.config_flow.async_get_usb_ports",
        side_effect=OSError("test_error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": True}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "usb_ports_failed"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_installed_already_configured(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
) -> None:
    """Test that only one unique instance is allowed when add-on is installed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "ws://localhost:3000",
            "usb_path": "/test",
            "network_key": "old123",
            "s0_legacy_key": "old123",
            "s2_access_control_key": "old456",
            "s2_authenticated_key": "old789",
            "s2_unauthenticated_key": "old987",
            "lr_s2_access_control_key": "old654",
            "lr_s2_authenticated_key": "old321",
        },
        title=TITLE,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/new",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == "/new"
    assert entry.data["s0_legacy_key"] == "new123"
    assert entry.data["s2_access_control_key"] == "new456"
    assert entry.data["s2_authenticated_key"] == "new789"
    assert entry.data["s2_unauthenticated_key"] == "new987"
    assert entry.data["lr_s2_access_control_key"] == "new654"
    assert entry.data["lr_s2_authenticated_key"] == "new321"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_addon_not_installed(
    hass: HomeAssistant,
    supervisor,
    addon_not_installed,
    install_addon,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
) -> None:
    """Test add-on not installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
            "lr_s2_access_control_key": "new654",
            "lr_s2_authenticated_key": "new321",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            }
        ),
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "lr_s2_access_control_key": "new654",
        "lr_s2_authenticated_key": "new321",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_install_addon_failure(
    hass: HomeAssistant, supervisor, addon_not_installed, install_addon
) -> None:
    """Test add-on install failure."""
    install_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


async def test_reconfigure_manual(hass: HomeAssistant, client, integration) -> None:
    """Test manual settings in reconfigure flow."""
    entry = integration
    hass.config_entries.async_update_entry(entry, unique_id="1234")

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "ws://1.1.1.1:3001"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == "ws://1.1.1.1:3001"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


async def test_reconfigure_manual_different_device(
    hass: HomeAssistant, integration
) -> None:
    """Test reconfigure flow manual step connecting to different device."""
    entry = integration
    hass.config_entries.async_update_entry(entry, unique_id="5678")

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "ws://1.1.1.1:3001"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"


async def test_reconfigure_not_addon(
    hass: HomeAssistant, client, supervisor, integration
) -> None:
    """Test reconfigure flow and opting out of add-on on Supervisor."""
    entry = integration
    hass.config_entries.async_update_entry(entry, unique_id="1234")

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:3000",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == "ws://localhost:3000"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.usefixtures("supervisor")
async def test_reconfigure_not_addon_with_addon(
    hass: HomeAssistant,
    setup_entry: AsyncMock,
    unload_entry: AsyncMock,
    integration: MockConfigEntry,
    stop_addon: AsyncMock,
) -> None:
    """Test reconfigure flow opting out of add-on on Supervisor with add-on."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "url": "ws://host1:3001", "use_addon": True},
        unique_id="1234",
    )

    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert unload_entry.call_count == 0
    setup_entry.reset_mock()

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert setup_entry.call_count == 0
    assert unload_entry.call_count == 1
    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:3000",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == "ws://localhost:3000"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert setup_entry.call_count == 1
    assert unload_entry.call_count == 1

    # avoid unload entry in teardown
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("supervisor")
async def test_reconfigure_not_addon_with_addon_stop_fail(
    hass: HomeAssistant,
    setup_entry: AsyncMock,
    unload_entry: AsyncMock,
    integration: MockConfigEntry,
    stop_addon: AsyncMock,
) -> None:
    """Test reconfigure flow opting out of add-on and add-on stop error."""
    stop_addon.side_effect = SupervisorError("Boom!")
    entry = integration
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "url": "ws://host1:3001", "use_addon": True},
        unique_id="1234",
    )

    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert unload_entry.call_count == 0
    setup_entry.reset_mock()

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )
    await hass.async_block_till_done()

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_stop_failed"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["use_addon"] is True
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert setup_entry.call_count == 1
    assert unload_entry.call_count == 1

    # avoid unload entry in teardown
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    (
        "discovery_info",
        "entry_data",
        "old_addon_options",
        "new_addon_options",
        "disconnect_calls",
    ),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
        ),
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {"use_addon": True},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            1,
        ),
    ],
)
async def test_reconfigure_addon_running(
    hass: HomeAssistant,
    client,
    supervisor,
    integration,
    addon_running,
    addon_options,
    set_addon_options,
    restart_addon,
    get_addon_discovery_info,
    discovery_info,
    entry_data,
    old_addon_options,
    new_addon_options,
    disconnect_calls,
) -> None:
    """Test reconfigure flow and add-on already running on Supervisor."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(config=new_addon_options),
    )
    assert client.disconnect.call_count == disconnect_calls

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == new_addon_options["device"]
    assert entry.data["s0_legacy_key"] == new_addon_options["s0_legacy_key"]
    assert (
        entry.data["s2_access_control_key"]
        == new_addon_options["s2_access_control_key"]
    )
    assert (
        entry.data["s2_authenticated_key"] == new_addon_options["s2_authenticated_key"]
    )
    assert (
        entry.data["s2_unauthenticated_key"]
        == new_addon_options["s2_unauthenticated_key"]
    )
    assert (
        entry.data["lr_s2_access_control_key"]
        == new_addon_options["lr_s2_access_control_key"]
    )
    assert (
        entry.data["lr_s2_authenticated_key"]
        == new_addon_options["lr_s2_authenticated_key"]
    )
    assert entry.data["use_addon"] is True
    assert entry.data["integration_created_addon"] is False
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize(
    ("discovery_info", "entry_data", "old_addon_options", "new_addon_options"),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/test",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
                "emulate_hardware": False,
            },
        ),
    ],
)
async def test_reconfigure_addon_running_no_changes(
    hass: HomeAssistant,
    client,
    supervisor,
    integration,
    addon_running,
    addon_options,
    set_addon_options,
    restart_addon,
    get_addon_discovery_info,
    discovery_info,
    entry_data,
    old_addon_options,
    new_addon_options,
) -> None:
    """Test reconfigure flow without changes, and add-on already running on Supervisor."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_addon_options,
    )
    await hass.async_block_till_done()

    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_count == 0
    assert restart_addon.call_count == 0

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == new_addon_options["device"]
    assert entry.data["s0_legacy_key"] == new_addon_options["s0_legacy_key"]
    assert (
        entry.data["s2_access_control_key"]
        == new_addon_options["s2_access_control_key"]
    )
    assert (
        entry.data["s2_authenticated_key"] == new_addon_options["s2_authenticated_key"]
    )
    assert (
        entry.data["s2_unauthenticated_key"]
        == new_addon_options["s2_unauthenticated_key"]
    )
    assert (
        entry.data["lr_s2_access_control_key"]
        == new_addon_options["lr_s2_access_control_key"]
    )
    assert (
        entry.data["lr_s2_authenticated_key"]
        == new_addon_options["lr_s2_authenticated_key"]
    )
    assert entry.data["use_addon"] is True
    assert entry.data["integration_created_addon"] is False
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


async def different_device_server_version(*args):
    """Return server version for a device with different home id."""
    return VersionInfo(
        driver_version="mock-driver-version",
        server_version="mock-server-version",
        home_id=5678,
        min_schema_version=0,
        max_schema_version=1,
    )


@pytest.mark.parametrize(
    (
        "discovery_info",
        "entry_data",
        "old_addon_options",
        "new_addon_options",
        "disconnect_calls",
        "server_version_side_effect",
    ),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            different_device_server_version,
        ),
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            different_device_server_version,
        ),
    ],
)
async def test_reconfigure_different_device(
    hass: HomeAssistant,
    client,
    supervisor,
    integration,
    addon_running,
    addon_options,
    set_addon_options,
    restart_addon,
    get_addon_discovery_info,
    discovery_info,
    entry_data,
    old_addon_options,
    new_addon_options,
    disconnect_calls,
    server_version_side_effect,
) -> None:
    """Test reconfigure flow and configuring a different device."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    assert set_addon_options.call_count == 1
    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=new_addon_options)
    )
    assert client.disconnect.call_count == disconnect_calls
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 1
    assert restart_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    # Default emulate_hardware is False.
    addon_options = {"emulate_hardware": False} | old_addon_options
    # Legacy network key is not reset.
    addon_options.pop("network_key")

    assert set_addon_options.call_count == 2
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=addon_options)
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 2
    assert restart_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"
    assert entry.data == data
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize(
    (
        "discovery_info",
        "entry_data",
        "old_addon_options",
        "new_addon_options",
        "disconnect_calls",
        "restart_addon_side_effect",
    ),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            [SupervisorError(), None],
        ),
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            [
                SupervisorError(),
                SupervisorError(),
            ],
        ),
    ],
)
async def test_reconfigure_addon_restart_failed(
    hass: HomeAssistant,
    client,
    supervisor,
    integration,
    addon_running,
    addon_options,
    set_addon_options,
    restart_addon,
    get_addon_discovery_info,
    discovery_info,
    entry_data,
    old_addon_options,
    new_addon_options,
    disconnect_calls,
    restart_addon_side_effect,
) -> None:
    """Test reconfigure flow and add-on restart failure."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    assert set_addon_options.call_count == 1
    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=new_addon_options)
    )
    assert client.disconnect.call_count == disconnect_calls
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 1
    assert restart_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    # The legacy network key should not be reset.
    old_addon_options.pop("network_key")
    assert set_addon_options.call_count == 2
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=old_addon_options)
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 2
    assert restart_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"
    assert entry.data == data
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize(
    (
        "discovery_info",
        "entry_data",
        "old_addon_options",
        "new_addon_options",
        "disconnect_calls",
        "server_version_side_effect",
    ),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "abc123",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/test",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            aiohttp.ClientError("Boom"),
        ),
    ],
)
async def test_reconfigure_addon_running_server_info_failure(
    hass: HomeAssistant,
    client,
    supervisor,
    integration,
    addon_running,
    addon_options,
    set_addon_options,
    restart_addon,
    get_addon_discovery_info,
    discovery_info,
    entry_data,
    old_addon_options,
    new_addon_options,
    disconnect_calls,
    server_version_side_effect,
) -> None:
    """Test reconfigure flow and add-on already running with server info failure."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_addon_options,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert entry.data == data
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize(
    (
        "discovery_info",
        "entry_data",
        "old_addon_options",
        "new_addon_options",
        "disconnect_calls",
    ),
    [
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {},
            {
                "device": "/test",
                "network_key": "abc123",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
        ),
        (
            [
                Discovery(
                    addon="core_zwave_js",
                    service="zwave_js",
                    uuid=uuid4(),
                    config=ADDON_DISCOVERY_INFO,
                )
            ],
            {"use_addon": True},
            {
                "device": "/test",
                "network_key": "abc123",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
                "log_level": "info",
                "emulate_hardware": False,
            },
            1,
        ),
    ],
)
async def test_reconfigure_addon_not_installed(
    hass: HomeAssistant,
    client,
    supervisor,
    addon_not_installed,
    install_addon,
    integration,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
    discovery_info,
    entry_data,
    old_addon_options,
    new_addon_options,
    disconnect_calls,
) -> None:
    """Test reconfigure flow and add-on not installed on Supervisor."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=new_addon_options)
    )
    assert client.disconnect.call_count == disconnect_calls

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == new_addon_options["device"]
    assert entry.data["s0_legacy_key"] == new_addon_options["s0_legacy_key"]
    assert entry.data["use_addon"] is True
    assert entry.data["integration_created_addon"] is True
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test zeroconf discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=3000,
            type="_zwave-js-server._tcp.local.",
            properties={"homeId": "1234"},
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    with (
        patch(
            "homeassistant.components.zwave_js.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.zwave_js.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://127.0.0.1:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
        "lr_s2_access_control_key": None,
        "lr_s2_authenticated_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_migrate_no_addon(hass: HomeAssistant, integration) -> None:
    """Test migration flow fails when not using add-on."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry, unique_id="1234", data={**entry.data, "use_addon": False}
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_required"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_reconfigure_migrate_with_addon(
    hass: HomeAssistant,
    client,
    supervisor,
    integration,
    addon_running,
    restart_addon,
    set_addon_options,
    get_addon_discovery_info,
) -> None:
    """Test migration flow with add-on."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry,
        unique_id="1234",
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "usb_path": "/dev/ttyUSB0",
        },
    )

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm backup progress", {"bytesRead": 100, "total": 200}
        )
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    async def mock_restore_nvm(data: bytes):
        client.driver.controller.emit(
            "nvm convert progress",
            {"event": "nvm convert progress", "bytesRead": 100, "total": 200},
        )
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm restore progress",
            {"event": "nvm restore progress", "bytesWritten": 100, "total": 200},
        )

    client.driver.controller.async_restore_nvm = AsyncMock(side_effect=mock_restore_nvm)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes", MagicMock()) as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1
        assert len(events) == 1
        assert events[0].data["progress"] == 0.5
        events.clear()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"
    assert result["data_schema"].schema[CONF_USB_PATH]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USB_PATH: "/test",
        },
    )

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config={"device": "/test"})
    )

    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "restore_nvm"

    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert client.driver.controller.async_restore_nvm.call_count == 1
    assert len(events) == 2
    assert events[0].data["progress"] == 0.25
    assert events[1].data["progress"] == 0.75

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert integration.data["url"] == "ws://host1:3001"
    assert integration.data["usb_path"] == "/test"
    assert integration.data["use_addon"] is True


async def test_reconfigure_migrate_backup_failure(
    hass: HomeAssistant, integration, client
) -> None:
    """Test backup failure."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry, unique_id="1234", data={**entry.data, "use_addon": True}
    )

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=FailedCommand("test_error", "unknown_error")
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "backup_failed"


async def test_reconfigure_migrate_backup_file_failure(
    hass: HomeAssistant, integration, client
) -> None:
    """Test backup file failure."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry, unique_id="1234", data={**entry.data, "use_addon": True}
    )

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch(
        "pathlib.Path.write_bytes", MagicMock(side_effect=OSError("test_error"))
    ):
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "backup_failed"


@pytest.mark.usefixtures("supervisor", "addon_running", "get_addon_discovery_info")
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_reconfigure_migrate_start_addon_failure(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    restart_addon: AsyncMock,
    set_addon_options: AsyncMock,
) -> None:
    """Test add-on start failure during migration."""
    restart_addon.side_effect = SupervisorError("Boom!")
    entry = integration
    hass.config_entries.async_update_entry(
        entry, unique_id="1234", data={**entry.data, "use_addon": True}
    )

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )
    client.driver.controller.async_restore_nvm = AsyncMock(
        side_effect=FailedCommand("test_error", "unknown_error")
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes", MagicMock()) as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USB_PATH: "/test",
        },
    )

    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config={"device": "/test"})
    )

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_zwave_js",
                service="zwave_js",
                uuid=uuid4(),
                config=ADDON_DISCOVERY_INFO,
            )
        ]
    ],
)
async def test_reconfigure_migrate_restore_failure(
    hass: HomeAssistant,
    client,
    supervisor,
    integration,
    addon_running,
    restart_addon,
    set_addon_options,
    get_addon_discovery_info,
) -> None:
    """Test restore failure."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry, unique_id="1234", data={**entry.data, "use_addon": True}
    )

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )
    client.driver.controller.async_restore_nvm = AsyncMock(
        side_effect=FailedCommand("test_error", "unknown_error")
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes", MagicMock()) as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USB_PATH: "/test",
        },
    )

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "restore_nvm"

    await hass.async_block_till_done()

    assert client.driver.controller.async_restore_nvm.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "restore_failed"


async def test_get_driver_failure(hass: HomeAssistant, integration, client) -> None:
    """Test get driver failure."""
    entry = integration
    hass.config_entries.async_update_entry(
        integration, unique_id="1234", data={**integration.data, "use_addon": True}
    )
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    await hass.config_entries.async_unload(integration.entry_id)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "backup_failed"


async def test_hard_reset_failure(hass: HomeAssistant, integration, client) -> None:
    """Test hard reset failure."""
    entry = integration
    hass.config_entries.async_update_entry(
        integration, unique_id="1234", data={**integration.data, "use_addon": True}
    )

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )
    client.driver.async_hard_reset = AsyncMock(
        side_effect=FailedCommand("test_error", "unknown_error")
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes", MagicMock()) as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reset_failed"


async def test_choose_serial_port_usb_ports_failure(
    hass: HomeAssistant, integration, client
) -> None:
    """Test choose serial port usb ports failure."""
    entry = integration
    hass.config_entries.async_update_entry(
        integration, unique_id="1234", data={**integration.data, "use_addon": True}
    )

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "intent_migrate"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes", MagicMock()) as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"

    with patch(
        "homeassistant.components.zwave_js.config_flow.async_get_usb_ports",
        side_effect=OSError("test_error"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "usb_ports_failed"


async def test_configure_addon_usb_ports_failure(
    hass: HomeAssistant, integration, addon_installed, supervisor
) -> None:
    """Test configure addon usb ports failure."""
    entry = integration
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    with patch(
        "homeassistant.components.zwave_js.config_flow.async_get_usb_ports",
        side_effect=OSError("test_error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": True}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "usb_ports_failed"
