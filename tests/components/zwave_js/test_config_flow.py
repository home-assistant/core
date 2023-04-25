"""Test the Z-Wave JS config flow."""
import asyncio
from collections.abc import Generator
from copy import copy
from unittest.mock import DEFAULT, MagicMock, call, patch

import aiohttp
import pytest
from serial.tools.list_ports_common import ListPortInfo
from zwave_js_server.version import VersionInfo

from homeassistant import config_entries
from homeassistant.components import usb
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.components.zwave_js.config_flow import SERVER_VERSION_TIMEOUT, TITLE
from homeassistant.components.zwave_js.const import ADDON_SLUG, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ADDON_DISCOVERY_INFO = {
    "addon": "Z-Wave JS",
    "host": "host1",
    "port": 3001,
}


USB_DISCOVERY_INFO = usb.UsbServiceInfo(
    device="/dev/zwave",
    pid="AAAA",
    vid="AAAA",
    serial_number="1234",
    description="zwave radio",
    manufacturer="test",
)

NORTEK_ZIGBEE_DISCOVERY_INFO = usb.UsbServiceInfo(
    device="/dev/zigbee",
    pid="8A2A",
    vid="10C4",
    serial_number="1234",
    description="nortek zigbee radio",
    manufacturer="nortek",
)

CP2652_ZIGBEE_DISCOVERY_INFO = usb.UsbServiceInfo(
    device="/dev/zigbee",
    pid="EA60",
    vid="10C4",
    serial_number="",
    description="cp2652",
    manufacturer="generic",
)


@pytest.fixture(name="setup_entry")
def setup_entry_fixture():
    """Mock entry setup."""
    with patch(
        "homeassistant.components.zwave_js.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="supervisor")
def mock_supervisor_fixture():
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.zwave_js.config_flow.is_hassio", return_value=True
    ):
        yield


@pytest.fixture(name="discovery_info")
def discovery_info_fixture():
    """Return the discovery info from the supervisor."""
    return DEFAULT


@pytest.fixture(name="discovery_info_side_effect")
def discovery_info_side_effect_fixture():
    """Return the discovery info from the supervisor."""
    return None


@pytest.fixture(name="get_addon_discovery_info")
def mock_get_addon_discovery_info(discovery_info, discovery_info_side_effect):
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_discovery_info",
        side_effect=discovery_info_side_effect,
        return_value=discovery_info,
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info


@pytest.fixture(name="server_version_side_effect")
def server_version_side_effect_fixture():
    """Return the server version side effect."""
    return None


@pytest.fixture(name="get_server_version", autouse=True)
def mock_get_server_version(server_version_side_effect, server_version_timeout):
    """Mock server version."""
    version_info = VersionInfo(
        driver_version="mock-driver-version",
        server_version="mock-server-version",
        home_id=1234,
        min_schema_version=0,
        max_schema_version=1,
    )
    with patch(
        "homeassistant.components.zwave_js.config_flow.get_server_version",
        side_effect=server_version_side_effect,
        return_value=version_info,
    ) as mock_version, patch(
        "homeassistant.components.zwave_js.config_flow.SERVER_VERSION_TIMEOUT",
        new=server_version_timeout,
    ):
        yield mock_version


@pytest.fixture(name="server_version_timeout")
def mock_server_version_timeout():
    """Patch the timeout for getting server version."""
    return SERVER_VERSION_TIMEOUT


@pytest.fixture(name="addon_setup_time", autouse=True)
def mock_addon_setup_time():
    """Mock add-on setup sleep time."""
    with patch(
        "homeassistant.components.zwave_js.config_flow.ADDON_SETUP_TIMEOUT", new=0
    ) as addon_setup_time:
        yield addon_setup_time


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
def mock_list_ports_fixture(serial_port) -> Generator[MagicMock, None, None]:
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
def mock_usb_serial_by_id_fixture() -> Generator[MagicMock, None, None]:
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
    assert result["type"] == "form"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Z-Wave JS"
    assert result2["data"] == {
        "url": "ws://localhost:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
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
    ("flow", "flow_params"),
    [
        (
            "flow",
            lambda entry: {
                "handler": DOMAIN,
                "context": {"source": config_entries.SOURCE_USER},
            },
        ),
        ("options", lambda entry: {"handler": entry.entry_id}),
    ],
)
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
async def test_manual_errors(
    hass: HomeAssistant, integration, url, error, flow, flow_params
) -> None:
    """Test all errors with a manual set up."""
    entry = integration
    result = await getattr(hass.config_entries, flow).async_init(**flow_params(entry))

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    result = await getattr(hass.config_entries, flow).async_configure(
        result["flow_id"],
        {
            "url": url,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
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

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://1.1.1.1:3001",
        },
    )

    assert result["type"] == "abort"
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

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("discovery_info", "server_version_side_effect"),
    [({"config": ADDON_DISCOVERY_INFO}, asyncio.TimeoutError())],
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

    assert result["type"] == "abort"
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

    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://localhost:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
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

    assert result["type"] == "abort"
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
    assert result["type"] == "form"
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

    assert result2["type"] == "abort"
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

    assert result2["type"] == "abort"
    assert result2["reason"] == "not_zwave_js_addon"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_usb_discovery(
    hass: HomeAssistant,
    supervisor,
    addon_not_installed,
    install_addon,
    addon_options,
    get_addon_discovery_info,
    set_addon_options,
    start_addon,
) -> None:
    """Test usb discovery success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "progress"
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": USB_DISCOVERY_INFO.device,
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": USB_DISCOVERY_INFO.device,
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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
    assert result["type"] == "form"
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    # Make sure the discovered usb device is preferred.
    data_schema = result["data_schema"]
    assert data_schema({}) == {
        "s0_legacy_key": "",
        "s2_access_control_key": "",
        "s2_authenticated_key": "",
        "s2_unauthenticated_key": "",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": USB_DISCOVERY_INFO.device,
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": USB_DISCOVERY_INFO.device,
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


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
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
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
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["step_id"] == "install_addon"
    assert result["type"] == "progress"

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
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

    assert result["type"] == "form"
    assert result["step_id"] == "hassio_confirm"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_in_progress"


async def test_abort_usb_discovery_already_configured(
    hass: HomeAssistant, supervisor, addon_options
) -> None:
    """Test usb discovery flow is aborted when there is an existing entry."""
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
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_usb_discovery_requires_supervisor(hass: HomeAssistant) -> None:
    """Test usb discovery flow is aborted when there is no supervisor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "discovery_requires_supervisor"


async def test_usb_discovery_already_running(
    hass: HomeAssistant, supervisor, addon_running
) -> None:
    """Test usb discovery flow is aborted when the addon is running."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )
    assert result["type"] == "abort"
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
    assert result["type"] == "abort"
    assert result["reason"] == "not_zwave_device"


async def test_not_addon(hass: HomeAssistant, supervisor) -> None:
    """Test opting out of add-on on Supervisor."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "ws://localhost:3000",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://localhost:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": True}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
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
            {"config": ADDON_DISCOVERY_INFO},
            HassioAPIError(),
            None,
            None,
            "addon_get_discovery_info_failed",
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            None,
            asyncio.TimeoutError,
            None,
            "cannot_connect",
        ),
        (
            None,
            None,
            None,
            None,
            "addon_get_discovery_info_failed",
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            None,
            None,
            HassioAPIError(),
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

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "abort"
    assert result["reason"] == abort_reason


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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
        },
        title=TITLE,
        unique_id=1234,  # Unique ID is purposely set to int to test migration logic
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == "/test_new"
    assert entry.data["s0_legacy_key"] == "new123"
    assert entry.data["s2_access_control_key"] == "new456"
    assert entry.data["s2_authenticated_key"] == "new789"
    assert entry.data["s2_unauthenticated_key"] == "new987"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("discovery_info", "start_addon_side_effect"),
    [({"config": ADDON_DISCOVERY_INFO}, HassioAPIError())],
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

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "abort"
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize(
    ("discovery_info", "server_version_side_effect"),
    [
        (
            {"config": ADDON_DISCOVERY_INFO},
            asyncio.TimeoutError,
        ),
        (
            None,
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

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "abort"
    assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize(
    ("set_addon_options_side_effect", "discovery_info"),
    [(HassioAPIError(), {"config": ADDON_DISCOVERY_INFO})],
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

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "addon_set_config_failed"

    assert start_addon.call_count == 0


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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
        },
        title=TITLE,
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/new",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == "/new"
    assert entry.data["s0_legacy_key"] == "new123"
    assert entry.data["s2_access_control_key"] == "new456"
    assert entry.data["s2_authenticated_key"] == "new789"
    assert entry.data["s2_unauthenticated_key"] == "new987"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
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

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "usb_path": "/test",
            "s0_legacy_key": "new123",
            "s2_access_control_key": "new456",
            "s2_authenticated_key": "new789",
            "s2_unauthenticated_key": "new987",
        },
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "s0_legacy_key": "new123",
        "s2_access_control_key": "new456",
        "s2_authenticated_key": "new789",
        "s2_unauthenticated_key": "new987",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_install_addon_failure(
    hass: HomeAssistant, supervisor, addon_not_installed, install_addon
) -> None:
    """Test add-on install failure."""
    install_addon.side_effect = HassioAPIError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "progress"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "abort"
    assert result["reason"] == "addon_install_failed"


async def test_options_manual(hass: HomeAssistant, client, integration) -> None:
    """Test manual settings in options flow."""
    entry = integration
    entry.unique_id = "1234"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"url": "ws://1.1.1.1:3001"}
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert entry.data["url"] == "ws://1.1.1.1:3001"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


async def test_options_manual_different_device(
    hass: HomeAssistant, integration
) -> None:
    """Test options flow manual step connecting to different device."""
    entry = integration
    entry.unique_id = 5678

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"url": "ws://1.1.1.1:3001"}
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "different_device"


async def test_options_not_addon(
    hass: HomeAssistant, client, supervisor, integration
) -> None:
    """Test options flow and opting out of add-on on Supervisor."""
    entry = integration
    entry.unique_id = "1234"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"use_addon": False}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:3000",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert entry.data["url"] == "ws://localhost:3000"
    assert entry.data["use_addon"] is False
    assert entry.data["integration_created_addon"] is False
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
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            {"use_addon": True},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            1,
        ),
    ],
)
async def test_options_addon_running(
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
    """Test options flow and add-on already running on Supervisor."""
    addon_options.update(old_addon_options)
    entry = integration
    entry.unique_id = "1234"
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data)

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {"options": new_addon_options},
    )
    assert client.disconnect.call_count == disconnect_calls

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert restart_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
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
    assert entry.data["use_addon"] is True
    assert entry.data["integration_created_addon"] is False
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize(
    ("discovery_info", "entry_data", "old_addon_options", "new_addon_options"),
    [
        (
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/test",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
                "emulate_hardware": False,
            },
        ),
    ],
)
async def test_options_addon_running_no_changes(
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
    """Test options flow without changes, and add-on already running on Supervisor."""
    addon_options.update(old_addon_options)
    entry = integration
    entry.unique_id = "1234"
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data)

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_addon_options,
    )
    await hass.async_block_till_done()

    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_count == 0
    assert restart_addon.call_count == 0

    assert result["type"] == "create_entry"
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
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            different_device_server_version,
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            different_device_server_version,
        ),
    ],
)
async def test_options_different_device(
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
    """Test options flow and configuring a different device."""
    addon_options.update(old_addon_options)
    entry = integration
    entry.unique_id = "1234"
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data)

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    assert set_addon_options.call_count == 1
    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {"options": new_addon_options},
    )
    assert client.disconnect.call_count == disconnect_calls
    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 1
    assert restart_addon.call_args == call(hass, "core_zwave_js")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    # Default emulate_hardware is False.
    addon_options = {"emulate_hardware": False} | old_addon_options
    # Legacy network key is not reset.
    addon_options.pop("network_key")

    assert set_addon_options.call_count == 2
    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {"options": addon_options},
    )
    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 2
    assert restart_addon.call_args == call(hass, "core_zwave_js")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] == "abort"
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
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            [HassioAPIError(), None],
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "old123",
                "s0_legacy_key": "old123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            [
                HassioAPIError(),
                HassioAPIError(),
            ],
        ),
    ],
)
async def test_options_addon_restart_failed(
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
    """Test options flow and add-on restart failure."""
    addon_options.update(old_addon_options)
    entry = integration
    entry.unique_id = "1234"
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data)

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    assert set_addon_options.call_count == 1
    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {"options": new_addon_options},
    )
    assert client.disconnect.call_count == disconnect_calls
    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 1
    assert restart_addon.call_args == call(hass, "core_zwave_js")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    # The legacy network key should not be reset.
    old_addon_options.pop("network_key")
    assert set_addon_options.call_count == 2
    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {"options": old_addon_options},
    )
    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert restart_addon.call_count == 2
    assert restart_addon.call_args == call(hass, "core_zwave_js")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] == "abort"
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
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "abc123",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            {
                "usb_path": "/test",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
            aiohttp.ClientError("Boom"),
        ),
    ],
)
async def test_options_addon_running_server_info_failure(
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
    """Test options flow and add-on already running with server info failure."""
    addon_options.update(old_addon_options)
    entry = integration
    entry.unique_id = "1234"
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data)

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_addon_options,
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
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
            {"config": ADDON_DISCOVERY_INFO},
            {},
            {
                "device": "/test",
                "network_key": "abc123",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            0,
        ),
        (
            {"config": ADDON_DISCOVERY_INFO},
            {"use_addon": True},
            {
                "device": "/test",
                "network_key": "abc123",
                "s0_legacy_key": "abc123",
                "s2_access_control_key": "old456",
                "s2_authenticated_key": "old789",
                "s2_unauthenticated_key": "old987",
            },
            {
                "usb_path": "/new",
                "s0_legacy_key": "new123",
                "s2_access_control_key": "new456",
                "s2_authenticated_key": "new789",
                "s2_unauthenticated_key": "new987",
                "log_level": "info",
                "emulate_hardware": False,
            },
            1,
        ),
    ],
)
async def test_options_addon_not_installed(
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
    """Test options flow and add-on not installed on Supervisor."""
    addon_options.update(old_addon_options)
    entry = integration
    entry.unique_id = "1234"
    data = {**entry.data, **entry_data}
    hass.config_entries.async_update_entry(entry, data=data)

    assert entry.data["url"] == "ws://test.org"

    assert client.connect.call_count == 1
    assert client.disconnect.call_count == 0

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "install_addon"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_configure(result["flow_id"])

    assert install_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        new_addon_options,
    )

    new_addon_options["device"] = new_addon_options.pop("usb_path")
    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {"options": new_addon_options},
    )
    assert client.disconnect.call_count == disconnect_calls

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    await hass.async_block_till_done()

    assert start_addon.call_count == 1
    assert start_addon.call_args == call(hass, "core_zwave_js")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert entry.data["url"] == "ws://host1:3001"
    assert entry.data["usb_path"] == new_addon_options["device"]
    assert entry.data["s0_legacy_key"] == new_addon_options["s0_legacy_key"]
    assert entry.data["use_addon"] is True
    assert entry.data["integration_created_addon"] is True
    assert client.connect.call_count == 2
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_import_addon_installed(
    hass: HomeAssistant,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
    serial_port,
) -> None:
    """Test import step while add-on already installed on Supervisor."""
    serial_port.device = "/test/imported"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"usb_path": "/test/imported", "network_key": "imported123"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "configure_addon"

    # the default input should be the imported data
    default_input = result["data_schema"]({})

    assert default_input == {
        "usb_path": "/test/imported",
        "s0_legacy_key": "imported123",
        "s2_access_control_key": "",
        "s2_authenticated_key": "",
        "s2_unauthenticated_key": "",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], default_input
    )

    assert set_addon_options.call_args == call(
        hass,
        "core_zwave_js",
        {
            "options": {
                "device": "/test/imported",
                "s0_legacy_key": "imported123",
                "s2_access_control_key": "",
                "s2_authenticated_key": "",
                "s2_unauthenticated_key": "",
            }
        },
    )

    assert result["type"] == "progress"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert start_addon.call_args == call(hass, "core_zwave_js")

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test/imported",
        "s0_legacy_key": "imported123",
        "s2_access_control_key": "",
        "s2_authenticated_key": "",
        "s2_unauthenticated_key": "",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test zeroconf discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            host="localhost",
            addresses=["127.0.0.1"],
            hostname="mock_hostname",
            name="mock_name",
            port=3000,
            type="_zwave-js-server._tcp.local.",
            properties={"homeId": "1234"},
        ),
    )

    assert result["type"] == "form"
    assert result["step_id"] == "zeroconf_confirm"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://localhost:3000",
        "usb_path": None,
        "s0_legacy_key": None,
        "s2_access_control_key": None,
        "s2_authenticated_key": None,
        "s2_unauthenticated_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
