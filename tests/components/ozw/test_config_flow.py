"""Test the Z-Wave over MQTT config flow."""
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.ozw.config_flow import TITLE
from homeassistant.components.ozw.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry

ADDON_DISCOVERY_INFO = {
    "addon": "OpenZWave",
    "host": "host1",
    "port": 1234,
    "username": "name1",
    "password": "pass1",
}


@pytest.fixture(name="supervisor")
def mock_supervisor_fixture():
    """Mock Supervisor."""
    with patch("homeassistant.components.hassio.is_hassio", return_value=True):
        yield


@pytest.fixture(name="addon_info")
def mock_addon_info():
    """Mock Supervisor add-on info."""
    with patch("homeassistant.components.hassio.async_get_addon_info") as addon_info:
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


@pytest.fixture(name="set_addon_options")
def mock_set_addon_options():
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.hassio.async_set_addon_options"
    ) as set_options:
        yield set_options


@pytest.fixture(name="install_addon")
def mock_install_addon():
    """Mock install add-on."""
    with patch("homeassistant.components.hassio.async_install_addon") as install_addon:
        yield install_addon


@pytest.fixture(name="start_addon")
def mock_start_addon():
    """Mock start add-on."""
    with patch("homeassistant.components.hassio.async_start_addon") as start_addon:
        yield start_addon


async def test_user_not_supervisor_create_entry(hass):
    """Test the user step creates an entry not on Supervisor."""
    hass.config.components.add("mqtt")
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.ozw.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ozw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": None,
        "network_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_mqtt_not_setup(hass):
    """Test that mqtt is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "mqtt_required"


async def test_one_instance_allowed(hass):
    """Test that only one instance is allowed."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title=TITLE)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_not_addon(hass, supervisor):
    """Test opting out of add-on on Supervisor."""
    hass.config.components.add("mqtt")
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ozw.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ozw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": False}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": None,
        "network_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_addon_running(hass, supervisor, addon_running, addon_options):
    """Test add-on already running on Supervisor."""
    addon_options["device"] = "/test"
    addon_options["network_key"] = "abc123"
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ozw.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ozw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": True}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": "/test",
        "network_key": "abc123",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_addon_info_failure(hass, supervisor, addon_info):
    """Test add-on info failure."""
    addon_info.side_effect = HassioAPIError()
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "addon_info_failed"


async def test_addon_installed(
    hass, supervisor, addon_installed, addon_options, set_addon_options, start_addon
):
    """Test add-on already installed but not running on Supervisor."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    with patch(
        "homeassistant.components.ozw.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ozw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": "/test",
        "network_key": "abc123",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_set_addon_config_failure(
    hass, supervisor, addon_installed, addon_options, set_addon_options
):
    """Test add-on set config failure."""
    set_addon_options.side_effect = HassioAPIError()
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "addon_set_config_failed"


async def test_start_addon_failure(
    hass, supervisor, addon_installed, addon_options, set_addon_options, start_addon
):
    """Test add-on start failure."""
    start_addon.side_effect = HassioAPIError()
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "addon_start_failed"}


async def test_addon_not_installed(
    hass,
    supervisor,
    addon_installed,
    install_addon,
    addon_options,
    set_addon_options,
    start_addon,
):
    """Test add-on not installed."""
    addon_installed.return_value["version"] = None
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
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
        "homeassistant.components.ozw.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ozw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"usb_path": "/test", "network_key": "abc123"}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_addon": True}
    )

    assert result["type"] == "progress"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "abort"
    assert result["reason"] == "addon_install_failed"


async def test_supervisor_discovery(hass, supervisor, addon_running, addon_options):
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
        "homeassistant.components.ozw.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ozw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": "/test",
        "network_key": "abc123",
        "use_addon": True,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_clean_discovery_on_user_create(
    hass, supervisor, addon_running, addon_options
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

    with patch(
        "homeassistant.components.ozw.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ozw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"use_addon": False}
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": None,
        "network_key": None,
        "use_addon": False,
        "integration_created_addon": False,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_discovery_with_user_flow(
    hass, supervisor, addon_running, addon_options
):
    """Test discovery flow is aborted if a user flow is in progress."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_abort_discovery_with_existing_entry(
    hass, supervisor, addon_running, addon_options
):
    """Test discovery flow is aborted if an entry already exists."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(domain=DOMAIN, data={}, title=TITLE, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


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
