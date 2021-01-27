"""Test the Z-Wave JS config flow."""
import asyncio
from unittest.mock import patch

import pytest
from zwave_js_server.version import VersionInfo

from homeassistant import config_entries, setup
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.zwave_js.config_flow import TITLE
from homeassistant.components.zwave_js.const import DOMAIN

from tests.common import MockConfigEntry

ADDON_DISCOVERY_INFO = {
    "addon": "Z-Wave JS",
    "host": "host1",
    "port": 3001,
}


@pytest.fixture(name="supervisor")
def mock_supervisor_fixture():
    """Mock Supervisor."""
    with patch("homeassistant.components.hassio.is_hassio", return_value=True):
        yield


@pytest.fixture(name="addon_info_side_effect")
def addon_info_side_effect_fixture():
    """Return the add-on info side effect."""
    return None


@pytest.fixture(name="addon_info")
def mock_addon_info(addon_info_side_effect):
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.hassio.async_get_addon_info",
        side_effect=addon_info_side_effect,
    ) as addon_info:
        addon_info.return_value = {}
        yield addon_info


@pytest.fixture(name="addon_running")
def mock_addon_running(addon_info):
    """Mock add-on already running."""
    addon_info.return_value["state"] = "started"
    return addon_info


@pytest.fixture(name="addon_installed")
def mock_addon_installed(addon_info):
    """Mock add-on already installed but not running."""
    addon_info.return_value["state"] = "stopped"
    addon_info.return_value["version"] = "1.0"
    return addon_info


@pytest.fixture(name="addon_options")
def mock_addon_options(addon_info):
    """Mock add-on options."""
    addon_info.return_value["options"] = {}
    return addon_info.return_value["options"]


@pytest.fixture(name="set_addon_options_side_effect")
def set_addon_options_side_effect_fixture():
    """Return the set add-on options side effect."""
    return None


@pytest.fixture(name="set_addon_options")
def mock_set_addon_options(set_addon_options_side_effect):
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.hassio.async_set_addon_options",
        side_effect=set_addon_options_side_effect,
    ) as set_options:
        yield set_options


@pytest.fixture(name="install_addon")
def mock_install_addon():
    """Mock install add-on."""
    with patch("homeassistant.components.hassio.async_install_addon") as install_addon:
        yield install_addon


@pytest.fixture(name="start_addon_side_effect")
def start_addon_side_effect_fixture():
    """Return the set add-on options side effect."""
    return None


@pytest.fixture(name="start_addon")
def mock_start_addon(start_addon_side_effect):
    """Mock start add-on."""
    with patch(
        "homeassistant.components.hassio.async_start_addon",
        side_effect=start_addon_side_effect,
    ) as start_addon:
        yield start_addon


@pytest.fixture(name="server_version_side_effect")
def server_version_side_effect_fixture():
    """Return the server version side effect."""
    return None


@pytest.fixture(name="get_server_version", autouse=True)
def mock_get_server_version(server_version_side_effect):
    """Mock server version."""
    version_info = VersionInfo(
        driver_version="mock-driver-version",
        server_version="mock-server-version",
        home_id=1234,
    )
    with patch(
        "homeassistant.components.zwave_js.config_flow.get_server_version",
        side_effect=server_version_side_effect,
        return_value=version_info,
    ) as mock_version:
        yield mock_version


@pytest.fixture(name="addon_setup_time", autouse=True)
def mock_addon_setup_time():
    """Mock add-on setup sleep time."""
    with patch(
        "homeassistant.components.zwave_js.config_flow.ADDON_SETUP_TIME", new=0
    ) as addon_setup_time:
        yield addon_setup_time


async def test_manual(hass):
    """Test we create an entry with manual step."""
    await setup.async_setup_component(hass, "persistent_notification", {})
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
        "network_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id == 1234


@pytest.mark.parametrize(
    "url, server_version_side_effect, error",
    [
        (
            "not-ws-url",
            None,
            "invalid_ws_url",
        ),
        (
            "ws://localhost:3000",
            asyncio.TimeoutError,
            "cannot_connect",
        ),
        (
            "ws://localhost:3000",
            Exception("Boom"),
            "unknown",
        ),
    ],
)
async def test_manual_errors(
    hass,
    url,
    error,
):
    """Test all errors with a manual set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": url,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": error}


async def test_manual_already_configured(hass):
    """Test that only one unique instance is allowed."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title=TITLE, unique_id=1234)
    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": "ws://localhost:3000",
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_supervisor_discovery(
    hass, supervisor, addon_running, addon_options, get_addon_discovery_info
):
    """Test flow started from Supervisor discovery."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    addon_options["device"] = "/test"
    addon_options["network_key"] = "abc123"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
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
        "network_key": "abc123",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "discovery_info, server_version_side_effect",
    [({"config": ADDON_DISCOVERY_INFO}, asyncio.TimeoutError())],
)
async def test_supervisor_discovery_cannot_connect(
    hass, supervisor, get_addon_discovery_info
):
    """Test Supervisor discovery and cannot connect."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_clean_discovery_on_user_create(
    hass, supervisor, addon_running, addon_options, get_addon_discovery_info
):
    """Test discovery flow is cleaned up when a user flow is finished."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    addon_options["device"] = "/test"
    addon_options["network_key"] = "abc123"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
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
        "network_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_discovery_with_existing_entry(
    hass, supervisor, addon_running, addon_options
):
    """Test discovery flow is aborted if an entry already exists."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://localhost:3000"}, title=TITLE, unique_id=1234
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    # Assert that the entry data is updated with discovery info.
    assert entry.data["url"] == "ws://host1:3001"


async def test_discovery_addon_not_running(
    hass, supervisor, addon_installed, addon_options, set_addon_options, start_addon
):
    """Test discovery with add-on already installed but not running."""
    addon_options["device"] = None
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["step_id"] == "hassio_confirm"
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["step_id"] == "start_addon"
    assert result["type"] == "form"


async def test_discovery_addon_not_installed(
    hass, supervisor, addon_installed, install_addon, addon_options
):
    """Test discovery with add-on not installed."""
    addon_installed.return_value["version"] = None
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["step_id"] == "hassio_confirm"
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["step_id"] == "install_addon"
    assert result["type"] == "progress"

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "form"
    assert result["step_id"] == "start_addon"


async def test_not_addon(hass, supervisor):
    """Test opting out of add-on on Supervisor."""
    await setup.async_setup_component(hass, "persistent_notification", {})

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
        "network_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_addon_running(
    hass,
    supervisor,
    addon_running,
    addon_options,
    get_addon_discovery_info,
):
    """Test add-on already running on Supervisor."""
    addon_options["device"] = "/test"
    addon_options["network_key"] = "abc123"
    await setup.async_setup_component(hass, "persistent_notification", {})

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
        "network_key": "abc123",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "discovery_info, discovery_info_side_effect, server_version_side_effect, "
    "addon_info_side_effect, abort_reason",
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
            "addon_missing_discovery_info",
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
    hass,
    supervisor,
    addon_running,
    get_addon_discovery_info,
    abort_reason,
):
    """Test all failures when add-on is running."""
    await setup.async_setup_component(hass, "persistent_notification", {})

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
    hass, supervisor, addon_running, get_addon_discovery_info
):
    """Test that only one unique instance is allowed when add-on is running."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title=TITLE, unique_id=1234)
    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
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


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_addon_installed(
    hass,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
):
    """Test add-on already installed but not running on Supervisor."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "network_key": "abc123",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "discovery_info, start_addon_side_effect",
    [({"config": ADDON_DISCOVERY_INFO}, HassioAPIError())],
)
async def test_addon_installed_start_failure(
    hass,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
):
    """Test add-on start failure when add-on is installed."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "start_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "addon_start_failed"}


@pytest.mark.parametrize(
    "set_addon_options_side_effect, start_addon_side_effect, discovery_info, "
    "server_version_side_effect, abort_reason",
    [
        (
            HassioAPIError(),
            None,
            {"config": ADDON_DISCOVERY_INFO},
            None,
            "addon_set_config_failed",
        ),
        (
            None,
            None,
            {"config": ADDON_DISCOVERY_INFO},
            asyncio.TimeoutError,
            "cannot_connect",
        ),
        (
            None,
            None,
            None,
            None,
            "addon_missing_discovery_info",
        ),
    ],
)
async def test_addon_installed_failures(
    hass,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
    abort_reason,
):
    """Test all failures when add-on is installed."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "start_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == abort_reason


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_addon_installed_already_configured(
    hass,
    supervisor,
    addon_installed,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
):
    """Test that only one unique instance is allowed when add-on is installed."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title=TITLE, unique_id=1234)
    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "start_addon"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("discovery_info", [{"config": ADDON_DISCOVERY_INFO}])
async def test_addon_not_installed(
    hass,
    supervisor,
    addon_installed,
    install_addon,
    addon_options,
    set_addon_options,
    start_addon,
    get_addon_discovery_info,
):
    """Test add-on not installed."""
    addon_installed.return_value["version"] = None
    await setup.async_setup_component(hass, "persistent_notification", {})

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

    assert result["type"] == "form"
    assert result["step_id"] == "start_addon"

    with patch(
        "homeassistant.components.zwave_js.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_js.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "url": "ws://host1:3001",
        "usb_path": "/test",
        "network_key": "abc123",
        "use_addon": True,
        "integration_created_addon": True,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_install_addon_failure(hass, supervisor, addon_installed, install_addon):
    """Test add-on install failure."""
    addon_installed.return_value["version"] = None
    install_addon.side_effect = HassioAPIError()
    await setup.async_setup_component(hass, "persistent_notification", {})

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

    assert result["type"] == "abort"
    assert result["reason"] == "addon_install_failed"
