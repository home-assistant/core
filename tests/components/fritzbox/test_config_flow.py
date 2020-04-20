"""Tests for AVM Fritz!Box config flow."""
from unittest import mock
from unittest.mock import Mock, patch

from pyfritzhome import LoginError
import pytest

from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_FRIENDLY_NAME
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

from . import MOCK_CONFIG

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
MOCK_SSDP_DATA = {
    ATTR_SSDP_LOCATION: "https://fake_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "fake_name",
}


@pytest.fixture(name="fritz")
def fritz_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.fritzbox.config_flow.Fritzhome") as fritz:
        yield fritz


async def test_user(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_host"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_PASSWORD] == "fake_pass"
    assert result["data"][CONF_USERNAME] == "fake_user"


async def test_user_auth_failed(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow by user with authentication failure."""
    fritz().login.side_effect = [LoginError("Boom"), mock.DEFAULT]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "auth_failed"


async def test_user_not_successful(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow by user but no connection found."""
    fritz().login.side_effect = OSError("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_found"


async def test_user_already_configured(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow by user when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow by import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_host"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_PASSWORD] == "fake_pass"
    assert result["data"][CONF_USERNAME] == "fake_user"


async def test_ssdp(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "fake_pass", CONF_USERNAME: "fake_user"},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_name"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_PASSWORD] == "fake_pass"
    assert result["data"][CONF_USERNAME] == "fake_user"


async def test_ssdp_auth_failed(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery with authentication failure."""
    fritz().login.side_effect = LoginError("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "whatever", CONF_USERNAME: "whatever"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["errors"]["base"] == "auth_failed"


async def test_ssdp_not_successful(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery but no device found."""
    fritz().login.side_effect = OSError("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "whatever", CONF_USERNAME: "whatever"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_found"


async def test_ssdp_already_in_progress(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_ssdp_already_configured(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
