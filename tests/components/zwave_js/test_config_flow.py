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
from voluptuous import InInvalid
from zwave_js_server.exceptions import FailedCommand
from zwave_js_server.model.node import Node
from zwave_js_server.version import VersionInfo

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.zwave_js.config_flow import TITLE, get_usb_ports
from homeassistant.components.zwave_js.const import (
    ADDON_SLUG,
    CONF_ADDON_DEVICE,
    CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_LR_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
    CONF_ADDON_SOCKET,
    CONF_SOCKET_PATH,
    CONF_USB_PATH,
    DOMAIN,
)
from homeassistant.components.zwave_js.helpers import SERVER_VERSION_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.esphome import ESPHomeServiceInfo
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, async_capture_events

ADDON_DISCOVERY_INFO = {
    "addon": "Z-Wave JS",
    "host": "host1",
    "port": 3001,
}


ESPHOME_DISCOVERY_INFO = ESPHomeServiceInfo(
    name="mock-name",
    zwave_home_id=1234,
    ip_address="192.168.1.100",
    port=6053,
)

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


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(name="discovery_info", autouse=True)
def discovery_info_fixture() -> list[Discovery]:
    """Fixture to set up discovery info."""
    return [
        Discovery(
            addon="core_zwave_js",
            service="zwave_js",
            uuid=uuid4(),
            config=ADDON_DISCOVERY_INFO,
        )
    ]


@pytest.fixture(name="discovery_info_side_effect", autouse=True)
def discovery_info_side_effect_fixture() -> Any | None:
    """Return the discovery info from the supervisor."""
    return None


@pytest.fixture(name="get_addon_discovery_info", autouse=True)
def get_addon_discovery_info_fixture(get_addon_discovery_info: AsyncMock) -> AsyncMock:
    """Get add-on discovery info."""
    return get_addon_discovery_info


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


@pytest.fixture
def mock_sdk_version(client: MagicMock) -> Generator[None]:
    """Mock the SDK version of the controller."""
    original_sdk_version = client.driver.controller.data.get("sdkVersion")
    client.driver.controller.data["sdkVersion"] = "6.60"
    yield
    if original_sdk_version is not None:
        client.driver.controller.data["sdkVersion"] = original_sdk_version


@pytest.fixture(name="set_country", autouse=True)
def set_country_fixture(hass: HomeAssistant) -> Generator[None]:
    """Set the country for the test."""
    original_country = hass.config.country
    # Set a default country to avoid asking the user to select it.
    hass.config.country = "US"
    yield
    # Reset the country after the test.
    hass.config.country = original_country


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
        "socket_path": None,
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


async def slow_server_version(*args: Any) -> Any:
    """Simulate a slow server version."""
    await asyncio.sleep(0.1)


@pytest.mark.usefixtures("integration")
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
async def test_manual_errors(hass: HomeAssistant, url: str, error: str) -> None:
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
    hass: HomeAssistant,
    integration: MockConfigEntry,
    url: str,
    error: str,
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


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_supervisor_discovery(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor")
@pytest.mark.parametrize("server_version_side_effect", [TimeoutError()])
async def test_supervisor_discovery_cannot_connect(hass: HomeAssistant) -> None:
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


async def test_clean_discovery_on_user_create(
    hass: HomeAssistant,
    supervisor,
    addon_running,
    addon_options,
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_abort_discovery_with_existing_entry(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
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


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
async def test_abort_hassio_discovery_with_existing_flow(hass: HomeAssistant) -> None:
    """Test hassio discovery flow is aborted when another discovery has happened."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

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


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
async def test_abort_hassio_discovery_for_other_addon(hass: HomeAssistant) -> None:
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


@pytest.mark.usefixtures("supervisor", "addon_not_installed", "addon_info")
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
async def test_usb_discovery(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    mock_usb_serial_by_id: MagicMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
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

    assert mock_usb_serial_by_id.call_count == 1
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"
    assert result["menu_options"] == ["intent_recommended", "intent_custom"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_installed")
async def test_usb_discovery_addon_not_running(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
    mock_usb_serial_by_id: MagicMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test usb discovery when add-on is installed but not running."""
    addon_options["device"] = "/dev/incorrect_device"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )

    assert mock_usb_serial_by_id.call_count == 2
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

    data_schema = result["data_schema"]
    assert data_schema is not None
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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_usb_discovery_migration(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
    mock_usb_serial_by_id: MagicMock,
    set_addon_options: AsyncMock,
    restart_addon: AsyncMock,
    client: MagicMock,
    integration: MockConfigEntry,
    get_server_version: AsyncMock,
) -> None:
    """Test usb discovery migration."""
    addon_options["device"] = "/dev/ttyUSB0"
    entry = integration
    assert client.connect.call_count == 1
    assert entry.unique_id == "3245146787"
    hass.config_entries.async_update_entry(
        entry,
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "usb_path": "/dev/ttyUSB0",
        },
    )

    async def mock_restart_addon(addon_slug: str) -> None:
        client.driver.controller.data["homeId"] = 1234

    restart_addon.side_effect = mock_restart_addon

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm backup progress", {"bytesRead": 100, "total": 200}
        )
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    async def mock_restore_nvm(data: bytes, options: dict[str, bool] | None = None):
        client.driver.controller.emit(
            "nvm convert progress",
            {"event": "nvm convert progress", "bytesRead": 100, "total": 200},
        )
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm restore progress",
            {"event": "nvm restore progress", "bytesWritten": 100, "total": 200},
        )
        client.driver.controller.data["homeId"] = 3245146787
        client.driver.emit(
            "driver ready", {"event": "driver ready", "source": "driver"}
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

    assert mock_usb_serial_by_id.call_count == 2

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_usb_migration"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1
        assert len(events) == 1
        assert events[0].data["progress"] == 0.5
        events.clear()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                CONF_ADDON_DEVICE: USB_DISCOVERY_INFO.device,
            }
        ),
    )

    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    version_info = get_server_version.return_value
    version_info.home_id = 3245146787

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "restore_nvm"
    assert client.connect.call_count == 2

    await hass.async_block_till_done()
    assert client.connect.call_count == 4
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert client.driver.controller.async_restore_nvm.call_count == 1
    assert len(events) == 2
    assert events[0].data["progress"] == 0.25
    assert events[1].data["progress"] == 0.75

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == USB_DISCOVERY_INFO.device
    assert entry.data["socket_path"] is None
    assert entry.data["use_addon"] is True
    assert "keep_old_devices" not in entry.data
    assert entry.unique_id == "3245146787"


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_usb_discovery_migration_restore_driver_ready_timeout(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
    mock_usb_serial_by_id: MagicMock,
    set_addon_options: AsyncMock,
    restart_addon: AsyncMock,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test driver ready timeout after nvm restore during usb discovery migration."""
    addon_options["device"] = "/dev/ttyUSB0"
    entry = integration
    assert client.connect.call_count == 1
    assert entry.unique_id == "3245146787"
    hass.config_entries.async_update_entry(
        entry,
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "usb_path": "/dev/ttyUSB0",
        },
    )

    async def mock_restart_addon(addon_slug: str) -> None:
        client.driver.controller.data["homeId"] = 1234

    restart_addon.side_effect = mock_restart_addon

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm backup progress", {"bytesRead": 100, "total": 200}
        )
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    async def mock_restore_nvm(data: bytes, options: dict[str, bool] | None = None):
        client.driver.controller.emit(
            "nvm convert progress",
            {"event": "nvm convert progress", "bytesRead": 100, "total": 200},
        )
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm restore progress",
            {"event": "nvm restore progress", "bytesWritten": 100, "total": 200},
        )
        client.driver.controller.data["homeId"] = 3245146787

    client.driver.controller.async_restore_nvm = AsyncMock(side_effect=mock_restore_nvm)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )

    assert mock_usb_serial_by_id.call_count == 2

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_usb_migration"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1
        assert len(events) == 1
        assert events[0].data["progress"] == 0.5
        events.clear()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": USB_DISCOVERY_INFO.device,
            }
        ),
    )

    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    with patch(
        ("homeassistant.components.zwave_js.helpers.DRIVER_READY_EVENT_TIMEOUT"),
        new=0,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "restore_nvm"
        assert client.connect.call_count == 2

        await hass.async_block_till_done()
        assert client.connect.call_count == 3
        assert entry.state is config_entries.ConfigEntryState.LOADED
        assert client.driver.controller.async_restore_nvm.call_count == 1
        assert len(events) == 2
        assert events[0].data["progress"] == 0.25
        assert events[1].data["progress"] == 0.75

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == USB_DISCOVERY_INFO.device
    assert entry.data["socket_path"] is None
    assert entry.data["use_addon"] is True
    assert entry.unique_id == "1234"
    assert "keep_old_devices" in entry.data


@pytest.mark.usefixtures("supervisor", "addon_not_installed", "addon_info")
async def test_esphome_discovery(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test ESPHome discovery success path."""
    # Make sure it works only on hassio
    with patch(
        "homeassistant.components.zwave_js.config_flow.is_hassio", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ESPHOME},
            data=ESPHOME_DISCOVERY_INFO,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_hassio"

    # Test working version
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ESPHOME},
        data=ESPHOME_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"
    assert result["menu_options"] == ["intent_recommended", "intent_custom"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["step_id"] == "install_addon"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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
                "socket": "esphome://192.168.1.100:6053",
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
    assert result["result"].unique_id == str(ESPHOME_DISCOVERY_INFO.zwave_home_id)
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": None,
        "socket_path": "esphome://192.168.1.100:6053",
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


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
async def test_esphome_discovery_already_configured(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
    addon_options: dict[str, Any],
) -> None:
    """Test ESPHome discovery success path."""
    addon_options[CONF_ADDON_SOCKET] = "esphome://existing-device:6053"
    addon_options["another_key"] = "should_not_be_touched"

    entry = MockConfigEntry(
        entry_id="mock-entry-id",
        domain=DOMAIN,
        data={CONF_SOCKET_PATH: "esphome://existing-device:6053"},
        title=TITLE,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ESPHOME},
            data=ESPHOME_DISCOVERY_INFO,
        )

    mock_reload.assert_called_once_with(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Addon got updated
    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "socket": "esphome://192.168.1.100:6053",
                "another_key": "should_not_be_touched",
            }
        ),
    )


@pytest.mark.usefixtures("supervisor", "addon_installed")
async def test_discovery_addon_not_running(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
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
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_not_installed", "addon_info")
async def test_discovery_addon_not_installed(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
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
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_info")
async def test_abort_usb_discovery_with_existing_flow(hass: HomeAssistant) -> None:
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


@pytest.mark.usefixtures("supervisor", "addon_installed")
async def test_usb_discovery_with_existing_usb_flow(hass: HomeAssistant) -> None:
    """Test usb discovery allows more than one USB flow in progress."""
    first_usb_info = UsbServiceInfo(
        device="/dev/other_device",
        pid="AAAA",
        vid="AAAA",
        serial_number="5678",
        description="zwave radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=first_usb_info,
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result2["type"] is FlowResultType.MENU
    assert result2["step_id"] == "installation_type"

    usb_flows_in_progress = hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": config_entries.SOURCE_USB}
    )

    assert len(usb_flows_in_progress) == 2

    for flow in (result, result2):
        hass.config_entries.flow.async_abort(flow["flow_id"])

    assert len(hass.config_entries.flow.async_progress()) == 0


@pytest.mark.usefixtures("supervisor", "addon_info")
async def test_abort_usb_discovery_addon_required(hass: HomeAssistant) -> None:
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
    mock_usb_serial_by_id: MagicMock,
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
    assert mock_usb_serial_by_id.call_count == 2


@pytest.mark.usefixtures("supervisor", "addon_info")
@pytest.mark.parametrize(
    "usb_discovery_info",
    [CP2652_ZIGBEE_DISCOVERY_INFO],
)
async def test_abort_usb_discovery_aborts_specific_devices(
    hass: HomeAssistant,
    usb_discovery_info: UsbServiceInfo,
) -> None:
    """Test usb discovery flow is aborted on specific devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=usb_discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_zwave_device"


@pytest.mark.usefixtures("supervisor")
async def test_not_addon(hass: HomeAssistant) -> None:
    """Test opting out of add-on on Supervisor."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_addon_running(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_running")
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
    addon_options: dict[str, Any],
    abort_reason: str,
) -> None:
    """Test all failures when add-on is running."""
    addon_options["device"] = "/test"
    addon_options["network_key"] = "abc123"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_addon_running_already_configured(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
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
    assert entry.data["socket_path"] is None
    assert entry.data["s0_legacy_key"] == "new123"
    assert entry.data["s2_access_control_key"] == "new456"
    assert entry.data["s2_authenticated_key"] == "new789"
    assert entry.data["s2_unauthenticated_key"] == "new987"
    assert entry.data["lr_s2_access_control_key"] == "new654"
    assert entry.data["lr_s2_authenticated_key"] == "new321"


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
async def test_addon_installed(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test add-on already installed but not running on Supervisor."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
@pytest.mark.parametrize("start_addon_side_effect", [SupervisorError()])
async def test_addon_installed_start_failure(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test add-on start failure when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
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
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test all failures when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
@pytest.mark.parametrize("set_addon_options_side_effect", [SupervisorError()])
async def test_addon_installed_set_options_failure(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test all failures when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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


@pytest.mark.usefixtures("supervisor", "addon_installed")
async def test_addon_installed_usb_ports_failure(hass: HomeAssistant) -> None:
    """Test usb ports failure when add-on is installed."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
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


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info")
async def test_addon_installed_already_configured(
    hass: HomeAssistant,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/new",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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
    assert entry.data["socket_path"] is None
    assert entry.data["s0_legacy_key"] == "new123"
    assert entry.data["s2_access_control_key"] == "new456"
    assert entry.data["s2_authenticated_key"] == "new789"
    assert entry.data["s2_unauthenticated_key"] == "new987"
    assert entry.data["lr_s2_access_control_key"] == "new654"
    assert entry.data["lr_s2_authenticated_key"] == "new321"


@pytest.mark.usefixtures("supervisor", "addon_not_installed", "addon_info")
async def test_addon_not_installed(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test add-on not installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
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
    assert result["step_id"] == "configure_addon_user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "network_type": "existing",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_security_keys"

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
        "socket_path": None,
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


@pytest.mark.usefixtures("supervisor", "addon_not_installed")
async def test_install_addon_failure(
    hass: HomeAssistant,
    install_addon: AsyncMock,
) -> None:
    """Test add-on install failure."""
    install_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_custom"}
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


async def test_reconfigure_manual(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
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
    hass: HomeAssistant,
    integration: MockConfigEntry,
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


@pytest.mark.usefixtures("supervisor")
async def test_reconfigure_not_addon(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
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


@pytest.mark.usefixtures("supervisor", "addon_running")
@pytest.mark.parametrize(
    (
        "entry_data",
        "old_addon_options",
        "form_data",
        "new_addon_options",
        "disconnect_calls",
    ),
    [
        (
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
            },
            {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            0,
        ),
        (
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
            },
            {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            1,
        ),
    ],
)
async def test_reconfigure_addon_running(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    restart_addon: AsyncMock,
    entry_data: dict[str, Any],
    old_addon_options: dict[str, Any],
    form_data: dict[str, Any],
    new_addon_options: dict[str, Any],
    disconnect_calls: int,
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
    assert result["step_id"] == "configure_addon_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data
    )

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
    assert entry.data["usb_path"] == new_addon_options.get("device")
    assert entry.data["socket_path"] == new_addon_options.get("socket")
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


@pytest.mark.usefixtures("supervisor", "addon_running")
@pytest.mark.parametrize(
    ("entry_data", "old_addon_options", "form_data", "new_addon_options"),
    [
        (
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
                "usb_path": "/test",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
            },
            {
                "device": "/test",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "lr_s2_access_control_key": "old654",
                "lr_s2_authenticated_key": "old321",
            },
        ),
    ],
)
async def test_reconfigure_addon_running_no_changes(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    restart_addon: AsyncMock,
    entry_data: dict[str, Any],
    old_addon_options: dict[str, Any],
    form_data: dict[str, Any],
    new_addon_options: dict[str, Any],
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
    assert result["step_id"] == "configure_addon_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data
    )
    await hass.async_block_till_done()

    assert set_addon_options.call_count == 0
    assert restart_addon.call_count == 0

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == new_addon_options.get("device")
    assert entry.data["socket_path"] == new_addon_options.get("socket")
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


@pytest.mark.usefixtures("supervisor", "addon_running")
@pytest.mark.parametrize(
    (
        "entry_data",
        "old_addon_options",
        "form_data",
        "new_addon_options",
        "disconnect_calls",
        "server_version_side_effect",
    ),
    [
        (
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
            },
            {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            0,
            different_device_server_version,
        ),
        (
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
                "socket_path": "esphome://mock-host:6053",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            {
                "socket": "esphome://mock-host:6053",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            0,
            different_device_server_version,
        ),
    ],
)
async def test_reconfigure_different_device(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    restart_addon: AsyncMock,
    entry_data: dict[str, Any],
    old_addon_options: dict[str, Any],
    form_data: dict[str, Any],
    new_addon_options: dict[str, Any],
    disconnect_calls: int,
) -> None:
    """Test reconfigure flow and configuring a different device."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")
    client.driver.controller.data["homeId"] = 1234

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
    assert result["step_id"] == "configure_addon_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data
    )

    assert set_addon_options.call_count == 1
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

    addon_options = {} | old_addon_options
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


@pytest.mark.usefixtures("supervisor", "addon_running")
@pytest.mark.parametrize(
    (
        "entry_data",
        "old_addon_options",
        "form_data",
        "new_addon_options",
        "disconnect_calls",
        "restart_addon_side_effect",
    ),
    [
        (
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
            },
            {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            0,
            [SupervisorError(), None],
        ),
        (
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
            },
            {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
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
    client: MagicMock,
    integration: MockConfigEntry,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    restart_addon: AsyncMock,
    entry_data: dict[str, Any],
    old_addon_options: dict[str, Any],
    form_data: dict[str, Any],
    new_addon_options: dict[str, Any],
    disconnect_calls: int,
) -> None:
    """Test reconfigure flow and add-on restart failure."""
    addon_options.update(old_addon_options)
    entry = integration
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data, unique_id="1234")
    client.driver.controller.data["homeId"] = 1234

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
    assert result["step_id"] == "configure_addon_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data
    )

    assert set_addon_options.call_count == 1
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


@pytest.mark.usefixtures("supervisor", "addon_running", "restart_addon")
@pytest.mark.parametrize("server_version_side_effect", [aiohttp.ClientError("Boom")])
async def test_reconfigure_addon_running_server_info_failure(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
) -> None:
    """Test reconfigure flow and add-on already running with server info failure."""
    old_addon_options = {
        "device": "/test",
        "network_key": "abc123",
        "s0_legacy_key": "abc123",
        "s2_access_control_key": "old456",
        "s2_authenticated_key": "old789",
        "s2_unauthenticated_key": "old987",
        "lr_s2_access_control_key": "old654",
        "lr_s2_authenticated_key": "old321",
    }
    new_addon_options = {
        "usb_path": "/test",
        "s0_legacy_key": "abc123",
        "s2_access_control_key": "old456",
        "s2_authenticated_key": "old789",
        "s2_unauthenticated_key": "old987",
        "lr_s2_access_control_key": "old654",
        "lr_s2_authenticated_key": "old321",
    }
    addon_options.update(old_addon_options)
    entry = integration
    hass.config_entries.async_update_entry(entry, unique_id="1234")

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
    assert result["step_id"] == "configure_addon_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_addon_options
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert entry.data["url"] == "ws://test.org"
    assert set_addon_options.call_count == 0
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.usefixtures("supervisor", "addon_not_installed")
@pytest.mark.parametrize(
    (
        "entry_data",
        "old_addon_options",
        "form_data",
        "new_addon_options",
        "disconnect_calls",
    ),
    [
        (
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
            },
            {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            0,
        ),
        (
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
            },
            {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "lr_s2_access_control_key": "new654",
                "lr_s2_authenticated_key": "new321",
            },
            1,
        ),
    ],
)
async def test_reconfigure_addon_not_installed(
    hass: HomeAssistant,
    client: MagicMock,
    install_addon: AsyncMock,
    integration: MockConfigEntry,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    entry_data: dict[str, Any],
    old_addon_options: dict[str, Any],
    form_data: dict[str, Any],
    new_addon_options: dict[str, Any],
    disconnect_calls: int,
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
    assert result["step_id"] == "configure_addon_reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data
    )

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
    assert entry.data["usb_path"] == new_addon_options.get("device")
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
        "socket_path": None,
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


async def test_reconfigure_migrate_no_addon(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
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
    assert "keep_old_devices" not in entry.data


@pytest.mark.usefixtures("mock_sdk_version")
async def test_reconfigure_migrate_low_sdk_version(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test migration flow fails with too low controller SDK version."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry, unique_id="1234", data={**entry.data, "use_addon": True}
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_low_sdk_version"
    assert "keep_old_devices" not in entry.data


@pytest.mark.usefixtures("supervisor", "addon_running")
@pytest.mark.parametrize(
    (
        "form_data",
        "new_addon_options",
        "restore_server_version_side_effect",
        "final_unique_id",
        "keep_old_devices",
        "device_entry_count",
    ),
    [
        (
            {CONF_USB_PATH: "/test"},
            {CONF_ADDON_DEVICE: "/test"},
            None,
            "3245146787",
            False,
            2,
        ),
        (
            {CONF_SOCKET_PATH: "esphome://1.2.3.4:1234"},
            {CONF_ADDON_SOCKET: "esphome://1.2.3.4:1234"},
            aiohttp.ClientError("Boom"),
            "5678",
            True,
            4,
        ),
    ],
)
async def test_reconfigure_migrate_with_addon(
    hass: HomeAssistant,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    multisensor_6: Node,
    integration: MockConfigEntry,
    restart_addon: AsyncMock,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    get_server_version: AsyncMock,
    form_data: dict[str, Any],
    new_addon_options: dict,
    restore_server_version_side_effect: Exception | None,
    final_unique_id: str,
    keep_old_devices: bool,
    device_entry_count: int,
) -> None:
    """Test migration flow with add-on."""
    version_info = get_server_version.return_value
    entry = integration
    assert client.connect.call_count == 1
    assert client.driver.controller.home_id == 3245146787
    assert entry.unique_id == "3245146787"
    hass.config_entries.async_update_entry(
        entry,
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "usb_path": "/dev/ttyUSB0",
        },
    )
    addon_options["device"] = "/dev/ttyUSB0"

    controller_node = client.driver.controller.own_node
    controller_device_id = (
        f"{client.driver.controller.home_id}-{controller_node.node_id}"
    )
    controller_device_id_ext = (
        f"{controller_device_id}-{controller_node.manufacturer_id}:"
        f"{controller_node.product_type}:{controller_node.product_id}"
    )

    assert len(device_registry.devices) == 2
    # Verify there's a device entry for the controller.
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, controller_device_id)}
    )
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, controller_device_id_ext)}
    )
    assert device.manufacturer == "AEON Labs"
    assert device.model == "ZW090"
    assert device.name == "Z‐Stick Gen5 USB Controller"
    # Verify there's a device entry for the multisensor.
    sensor_device_id = f"{client.driver.controller.home_id}-{multisensor_6.node_id}"
    device = device_registry.async_get_device(identifiers={(DOMAIN, sensor_device_id)})
    assert device
    assert device.manufacturer == "AEON Labs"
    assert device.model == "ZW100"
    assert device.name == "Multisensor 6"
    # Customize the sensor device name.
    device_registry.async_update_device(
        device.id, name_by_user="Custom Sensor Device Name"
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

    async def mock_restore_nvm(data: bytes, options: dict[str, bool] | None = None):
        client.driver.controller.emit(
            "nvm convert progress",
            {"event": "nvm convert progress", "bytesRead": 100, "total": 200},
        )
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm restore progress",
            {"event": "nvm restore progress", "bytesWritten": 100, "total": 200},
        )
        client.driver.controller.data["homeId"] = 3245146787
        client.driver.emit(
            "driver ready", {"event": "driver ready", "source": "driver"}
        )

    client.driver.controller.async_restore_nvm = AsyncMock(side_effect=mock_restore_nvm)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1
        assert len(events) == 1
        assert events[0].data["progress"] == 0.5
        events.clear()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"

    version_info.home_id = 5678

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=new_addon_options)
    )

    # Simulate the new connected controller hardware labels.
    # This will cause a new device entry to be created
    # when the config entry is loaded before restoring NVM.
    controller_node = client.driver.controller.own_node
    controller_node.data["manufacturerId"] = 999
    controller_node.data["productId"] = 999
    controller_node.device_config.data["description"] = "New Device Name"
    controller_node.device_config.data["label"] = "New Device Model"
    controller_node.device_config.data["manufacturer"] = "New Device Manufacturer"
    client.driver.controller.data["homeId"] = 5678

    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    # Ensure add-on running would migrate the old settings back into the config entry
    with patch("homeassistant.components.zwave_js.async_ensure_addon_running"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert entry.unique_id == "5678"
        get_server_version.side_effect = restore_server_version_side_effect
        version_info.home_id = 3245146787

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "restore_nvm"
        assert client.connect.call_count == 2

        await hass.async_block_till_done()
    assert client.connect.call_count == 4
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert client.driver.controller.async_restore_nvm.call_count == 1
    assert len(events) == 2
    assert events[0].data["progress"] == 0.25
    assert events[1].data["progress"] == 0.75

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data[CONF_USB_PATH] == new_addon_options.get(CONF_ADDON_DEVICE)
    assert entry.data[CONF_SOCKET_PATH] == new_addon_options.get(CONF_ADDON_SOCKET)
    assert entry.data["use_addon"] is True
    assert ("keep_old_devices" in entry.data) is keep_old_devices
    assert entry.unique_id == final_unique_id

    assert len(device_registry.devices) == device_entry_count
    controller_device_id_ext = (
        f"{controller_device_id}-{controller_node.manufacturer_id}:"
        f"{controller_node.product_type}:{controller_node.product_id}"
    )
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, controller_device_id_ext)}
    )
    assert device
    assert device.manufacturer == "New Device Manufacturer"
    assert device.model == "New Device Model"
    assert device.name == "New Device Name"
    device = device_registry.async_get_device(identifiers={(DOMAIN, sensor_device_id)})
    assert device
    assert device.manufacturer == "AEON Labs"
    assert device.model == "ZW100"
    assert device.name == "Multisensor 6"
    assert device.name_by_user == "Custom Sensor Device Name"
    assert client.driver.controller.home_id == 3245146787


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_reconfigure_migrate_restore_driver_ready_timeout(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    restart_addon: AsyncMock,
    set_addon_options: AsyncMock,
) -> None:
    """Test migration flow with driver ready timeout after nvm restore."""
    entry = integration
    assert client.connect.call_count == 1
    assert client.driver.controller.home_id == 3245146787
    assert entry.unique_id == "3245146787"
    hass.config_entries.async_update_entry(
        entry,
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "usb_path": "/dev/ttyUSB0",
        },
    )

    async def mock_restart_addon(addon_slug: str) -> None:
        client.driver.controller.data["homeId"] = 1234

    restart_addon.side_effect = mock_restart_addon

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm backup progress", {"bytesRead": 100, "total": 200}
        )
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    async def mock_restore_nvm(data: bytes, options: dict[str, bool] | None = None):
        client.driver.controller.emit(
            "nvm convert progress",
            {"event": "nvm convert progress", "bytesRead": 100, "total": 200},
        )
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm restore progress",
            {"event": "nvm restore progress", "bytesWritten": 100, "total": 200},
        )
        client.driver.controller.data["homeId"] = 3245146787

    client.driver.controller.async_restore_nvm = AsyncMock(side_effect=mock_restore_nvm)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1
        assert len(events) == 1
        assert events[0].data["progress"] == 0.5
        events.clear()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert data_schema.schema[CONF_USB_PATH]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USB_PATH: "/test",
        },
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config={"device": "/test"})
    )

    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    with patch(
        ("homeassistant.components.zwave_js.helpers.DRIVER_READY_EVENT_TIMEOUT"),
        new=0,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "restore_nvm"
        assert client.connect.call_count == 2

        await hass.async_block_till_done()
        assert client.connect.call_count == 3
        assert entry.state is config_entries.ConfigEntryState.LOADED
        assert client.driver.controller.async_restore_nvm.call_count == 1
        assert len(events) == 2
        assert events[0].data["progress"] == 0.25
        assert events[1].data["progress"] == 0.75

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == "/test"
    assert entry.data["socket_path"] is None
    assert entry.data["use_addon"] is True
    assert "keep_old_devices" in entry.data
    assert entry.unique_id == "1234"


async def test_reconfigure_migrate_backup_failure(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    client: MagicMock,
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "backup_failed"
    assert "keep_old_devices" not in entry.data


async def test_reconfigure_migrate_backup_file_failure(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    client: MagicMock,
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes", side_effect=OSError("test_error")):
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "backup_failed"
    assert "keep_old_devices" not in entry.data


@pytest.mark.usefixtures("supervisor", "addon_running")
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

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"
    assert "keep_old_devices" not in entry.data


@pytest.mark.usefixtures("supervisor", "addon_running", "restart_addon")
async def test_reconfigure_migrate_restore_failure(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    set_addon_options: AsyncMock,
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USB_PATH: "/test",
        },
    )

    assert set_addon_options.call_count == 1
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "restore_nvm"

    await hass.async_block_till_done()

    assert client.driver.controller.async_restore_nvm.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "restore_failed"
    description_placeholders = result["description_placeholders"]
    assert description_placeholders is not None
    assert description_placeholders["file_path"]
    assert description_placeholders["file_url"]
    assert description_placeholders["file_name"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "restore_nvm"

    await hass.async_block_till_done()

    assert client.driver.controller.async_restore_nvm.call_count == 2

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "restore_failed"

    hass.config_entries.flow.async_abort(result["flow_id"])

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert "keep_old_devices" not in entry.data


async def test_get_driver_failure_intent_migrate(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test get driver failure in intent migrate step."""
    entry = integration
    hass.config_entries.async_update_entry(
        entry, unique_id="1234", data={**entry.data, "use_addon": True}
    )
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    await hass.config_entries.async_unload(entry.entry_id)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "config_entry_not_loaded"
    assert "keep_old_devices" not in entry.data


async def test_choose_serial_port_usb_ports_failure(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test choose serial port usb ports failure."""
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

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    with patch(
        "homeassistant.components.zwave_js.config_flow.async_get_usb_ports",
        side_effect=OSError("test_error"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "usb_ports_failed"


@pytest.mark.usefixtures("supervisor", "addon_installed")
async def test_configure_addon_usb_ports_failure(
    hass: HomeAssistant,
    integration: MockConfigEntry,
) -> None:
    """Test configure addon usb ports failure."""
    entry = integration
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_reconfigure"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor_reconfigure"

    with patch(
        "homeassistant.components.zwave_js.config_flow.async_get_usb_ports",
        side_effect=OSError("test_error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": True}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "usb_ports_failed"


async def test_get_usb_ports_filtering() -> None:
    """Test that get_usb_ports filters out 'n/a' descriptions when other ports are available."""
    mock_ports = [
        ListPortInfo("/dev/ttyUSB0"),
        ListPortInfo("/dev/ttyUSB1"),
        ListPortInfo("/dev/ttyUSB2"),
        ListPortInfo("/dev/ttyUSB3"),
    ]
    mock_ports[0].description = "n/a"
    mock_ports[1].description = "Device A"
    mock_ports[2].description = "N/A"
    mock_ports[3].description = "Device B"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that only non-"n/a" descriptions are returned
        assert descriptions == [
            "Device A - /dev/ttyUSB1, s/n: n/a",
            "Device B - /dev/ttyUSB3, s/n: n/a",
        ]


async def test_get_usb_ports_all_na() -> None:
    """Test that get_usb_ports returns all ports as-is when only 'n/a' descriptions exist."""
    mock_ports = [
        ListPortInfo("/dev/ttyUSB0"),
        ListPortInfo("/dev/ttyUSB1"),
        ListPortInfo("/dev/ttyUSB2"),
    ]
    mock_ports[0].description = "n/a"
    mock_ports[1].description = "N/A"
    mock_ports[2].description = "n/a"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that all ports are returned since they all have "n/a" descriptions
        assert len(descriptions) == 3
        # Verify that all descriptions contain "n/a" (case-insensitive)
        assert all("n/a" in desc.lower() for desc in descriptions)
        # Verify that all expected device paths are present
        device_paths = [desc.split(" - ")[1].split(",")[0] for desc in descriptions]
        assert "/dev/ttyUSB0" in device_paths
        assert "/dev/ttyUSB1" in device_paths
        assert "/dev/ttyUSB2" in device_paths


async def test_get_usb_ports_mixed_case_filtering() -> None:
    """Test that get_usb_ports filters out 'n/a' descriptions with different case variations."""
    mock_ports = [
        ListPortInfo("/dev/ttyUSB0"),
        ListPortInfo("/dev/ttyUSB1"),
        ListPortInfo("/dev/ttyUSB2"),
        ListPortInfo("/dev/ttyUSB3"),
        ListPortInfo("/dev/ttyUSB4"),
    ]
    mock_ports[0].description = "n/a"
    mock_ports[1].description = "Device A"
    mock_ports[2].description = "N/A"
    mock_ports[3].description = "n/A"
    mock_ports[4].description = "Device B"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that only non-"n/a" descriptions are returned (case-insensitive filtering)
        assert descriptions == [
            "Device A - /dev/ttyUSB1, s/n: n/a",
            "Device B - /dev/ttyUSB4, s/n: n/a",
        ]


async def test_get_usb_ports_empty_list() -> None:
    """Test that get_usb_ports handles empty port list."""
    with patch("serial.tools.list_ports.comports", return_value=[]):
        result = get_usb_ports()

        # Verify that empty dict is returned
        assert result == {}


async def test_get_usb_ports_single_na_port() -> None:
    """Test that get_usb_ports returns single 'n/a' port when it's the only one available."""
    mock_ports = [ListPortInfo("/dev/ttyUSB0")]
    mock_ports[0].description = "n/a"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that the single "n/a" port is returned
        assert descriptions == [
            "n/a - /dev/ttyUSB0, s/n: n/a",
        ]


async def test_get_usb_ports_single_valid_port() -> None:
    """Test that get_usb_ports returns single valid port."""
    mock_ports = [ListPortInfo("/dev/ttyUSB0")]
    mock_ports[0].description = "Device A"

    with patch("serial.tools.list_ports.comports", return_value=mock_ports):
        result = get_usb_ports()

        descriptions = list(result.values())

        # Verify that the single valid port is returned
        assert descriptions == [
            "Device A - /dev/ttyUSB0, s/n: n/a",
        ]


@pytest.mark.usefixtures("supervisor", "addon_not_installed", "addon_info")
async def test_intent_recommended_user(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    set_addon_options: AsyncMock,
) -> None:
    """Test the intent_recommended step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_recommended"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_addon_user"
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert len(data_schema.schema) == 2
    assert data_schema.schema.get(CONF_USB_PATH) is not None
    assert data_schema.schema.get(CONF_SOCKET_PATH) is not None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USB_PATH: "/test",
        },
    )

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                CONF_ADDON_DEVICE: "/test",
                CONF_ADDON_S0_LEGACY_KEY: "",
                CONF_ADDON_S2_ACCESS_CONTROL_KEY: "",
                CONF_ADDON_S2_AUTHENTICATED_KEY: "",
                CONF_ADDON_S2_UNAUTHENTICATED_KEY: "",
                CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY: "",
                CONF_ADDON_LR_S2_AUTHENTICATED_KEY: "",
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
        "socket_path": None,
        "s0_legacy_key": "",
        "s2_access_control_key": "",
        "s2_authenticated_key": "",
        "s2_unauthenticated_key": "",
        "lr_s2_access_control_key": "",
        "lr_s2_authenticated_key": "",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("supervisor", "addon_not_installed", "addon_info")
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
async def test_recommended_usb_discovery(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    mock_usb_serial_by_id: MagicMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
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

    assert mock_usb_serial_by_id.call_count == 1
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"
    assert result["menu_options"] == ["intent_recommended", "intent_custom"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_recommended"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": device,
                "s0_legacy_key": "",
                "s2_access_control_key": "",
                "s2_authenticated_key": "",
                "s2_unauthenticated_key": "",
                "lr_s2_access_control_key": "",
                "lr_s2_authenticated_key": "",
            }
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
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call("core_zwave_js")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": device,
        "socket_path": None,
        "s0_legacy_key": "",
        "s2_access_control_key": "",
        "s2_authenticated_key": "",
        "s2_unauthenticated_key": "",
        "lr_s2_access_control_key": "",
        "lr_s2_authenticated_key": "",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("supervisor", "addon_installed", "addon_info", "unload_entry")
async def test_addon_rf_region_new_network(
    hass: HomeAssistant,
    setup_entry: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test RF region selection for new network when country is None."""
    device = "/test"
    hass.config.country = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_recommended"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": device,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rf_region"

    # Check that all expected RF regions are available

    data_schema = result["data_schema"]
    assert data_schema is not None
    schema = data_schema.schema
    rf_region_field = schema["rf_region"]
    selector_options = rf_region_field.config["options"]

    expected_regions = [
        "Australia/New Zealand",
        "China",
        "Europe",
        "Hong Kong",
        "India",
        "Israel",
        "Japan",
        "Korea",
        "Russia",
        "USA",
    ]

    assert selector_options == expected_regions

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"rf_region": "Europe"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    # Verify RF region was set in addon config
    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": device,
                "s0_legacy_key": "",
                "s2_access_control_key": "",
                "s2_authenticated_key": "",
                "s2_unauthenticated_key": "",
                "lr_s2_access_control_key": "",
                "lr_s2_authenticated_key": "",
                "rf_region": "Europe",
            }
        ),
    )

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_zwave_js")
    assert setup_entry.call_count == 1

    # avoid unload entry in teardown
    entry = result["result"]
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("supervisor", "addon_running")
async def test_addon_rf_region_migrate_network(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
    restart_addon: AsyncMock,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    get_server_version: AsyncMock,
) -> None:
    """Test migration flow with add-on."""
    hass.config.country = None
    version_info = get_server_version.return_value
    entry = integration
    assert client.connect.call_count == 1
    assert client.driver.controller.home_id == 3245146787
    assert entry.unique_id == "3245146787"
    hass.config_entries.async_update_entry(
        entry,
        data={
            "url": "ws://localhost:3000",
            "use_addon": True,
            "usb_path": "/dev/ttyUSB0",
        },
    )
    addon_options["device"] = "/dev/ttyUSB0"

    async def mock_backup_nvm_raw():
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm backup progress", {"bytesRead": 100, "total": 200}
        )
        return b"test_nvm_data"

    client.driver.controller.async_backup_nvm_raw = AsyncMock(
        side_effect=mock_backup_nvm_raw
    )

    async def mock_restore_nvm(data: bytes, options: dict[str, bool] | None = None):
        client.driver.controller.emit(
            "nvm convert progress",
            {"event": "nvm convert progress", "bytesRead": 100, "total": 200},
        )
        await asyncio.sleep(0)
        client.driver.controller.emit(
            "nvm restore progress",
            {"event": "nvm restore progress", "bytesWritten": 100, "total": 200},
        )
        client.driver.controller.data["homeId"] = 3245146787
        client.driver.emit(
            "driver ready", {"event": "driver ready", "source": "driver"}
        )

    client.driver.controller.async_restore_nvm = AsyncMock(side_effect=mock_restore_nvm)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_migrate"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "backup_nvm"

    with patch("pathlib.Path.write_bytes") as mock_file:
        await hass.async_block_till_done()
        assert client.driver.controller.async_backup_nvm_raw.call_count == 1
        assert mock_file.call_count == 1
        assert len(events) == 1
        assert events[0].data["progress"] == 0.5
        events.clear()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "instruct_unplug"
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert data_schema.schema[CONF_USB_PATH]
    # Ensure the old usb path is not in the list of options
    with pytest.raises(InInvalid):
        data_schema.schema[CONF_USB_PATH](addon_options["device"])

    version_info.home_id = 5678

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USB_PATH: "/test",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rf_region"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"rf_region": "Europe"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": "/test",
                "rf_region": "Europe",
            }
        ),
    )

    await hass.async_block_till_done()

    assert restart_addon.call_args == call("core_zwave_js")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert entry.unique_id == "5678"
    version_info.home_id = 3245146787

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "restore_nvm"
    assert client.connect.call_count == 2

    await hass.async_block_till_done()
    assert client.connect.call_count == 4
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert client.driver.controller.async_restore_nvm.call_count == 1
    assert len(events) == 2
    assert events[0].data["progress"] == 0.25
    assert events[1].data["progress"] == 0.75

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == "/test"
    assert entry.data["socket_path"] is None
    assert entry.data["use_addon"] is True
    assert entry.unique_id == "3245146787"
    assert client.driver.controller.home_id == 3245146787


@pytest.mark.usefixtures("supervisor", "addon_installed", "unload_entry")
@pytest.mark.parametrize(("country", "rf_region"), [("US", "Automatic"), (None, "USA")])
async def test_addon_skip_rf_region(
    hass: HomeAssistant,
    setup_entry: AsyncMock,
    addon_options: dict[str, Any],
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    country: str | None,
    rf_region: str,
) -> None:
    """Test RF region selection is skipped if not needed."""
    device = "/test"
    addon_options["rf_region"] = rf_region
    hass.config.country = country

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "installation_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "intent_recommended"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": device,
        },
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"

    # Verify RF region was set in addon config
    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        "core_zwave_js",
        AddonsOptions(
            config={
                "device": device,
                "s0_legacy_key": "",
                "s2_access_control_key": "",
                "s2_authenticated_key": "",
                "s2_unauthenticated_key": "",
                "lr_s2_access_control_key": "",
                "lr_s2_authenticated_key": "",
                "rf_region": rf_region,
            }
        ),
    )

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_zwave_js")
    assert setup_entry.call_count == 1

    # avoid unload entry in teardown
    entry = result["result"]
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
