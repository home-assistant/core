"""Test the Z-Wave over MQTT config flow."""
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.ozw.config_flow import TITLE
from homeassistant.components.ozw.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture(name="supervisor")
def mock_supervisor_fixture():
    """Mock Supervisor."""
    with patch("homeassistant.components.hassio.is_hassio", return_value=True):
        yield


@pytest.fixture(name="addon_info")
def mock_addon_info():
    """Mock Supervisor add-on info."""
    with patch("homeassistant.components.hassio.async_get_addon_info") as addon_info:
        yield addon_info


@pytest.fixture(name="addon_running")
def mock_addon_running(addon_info):
    """Mock add-on already running."""
    addon_info.return_value = {"state": "started"}
    return addon_info


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

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": None,
        "network_key": None,
        "integration_created_addon": False,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_addon_running(hass, supervisor, addon_running):
    """Test add-on already running on Supervisor."""
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
            result["flow_id"], {"use_addon": True}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert result["data"] == {
        "usb_path": None,
        "network_key": None,
        "integration_created_addon": False,
    }
    await hass.async_block_till_done()
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
