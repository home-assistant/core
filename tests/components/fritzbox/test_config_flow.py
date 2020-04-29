"""Tests for AVM Fritz!Box config flow."""
from unittest import mock
from unittest.mock import Mock, patch

from pyfritzhome import LoginError
import pytest
from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

from . import MOCK_CONFIG

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
MOCK_SSDP_DATA = {
    ATTR_SSDP_LOCATION: "https://fake_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "fake_name",
    ATTR_UPNP_UDN: "uuid:only-a-test",
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
    assert not result["result"].unique_id


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
    assert not result["result"].unique_id

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
    assert not result["result"].unique_id


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
    assert result["result"].unique_id == "only-a-test"


async def test_ssdp_no_friendly_name(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery without friendly name."""
    MOCK_NO_NAME = MOCK_SSDP_DATA.copy()
    del MOCK_NO_NAME[ATTR_UPNP_FRIENDLY_NAME]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_NO_NAME
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "fake_pass", CONF_USERNAME: "fake_user"},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "fake_host"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_PASSWORD] == "fake_pass"
    assert result["data"][CONF_USERNAME] == "fake_user"
    assert result["result"].unique_id == "only-a-test"


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


async def test_ssdp_not_supported(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery with unsupported device."""
    fritz().get_device_elements.side_effect = HTTPError("Boom")

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
    assert result["reason"] == "not_supported"


async def test_ssdp_already_in_progress_unique_id(hass: HomeAssistantType, fritz: Mock):
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


async def test_ssdp_already_in_progress_host(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    MOCK_NO_UNIQUE_ID = MOCK_SSDP_DATA.copy()
    del MOCK_NO_UNIQUE_ID[ATTR_UPNP_UDN]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_NO_UNIQUE_ID
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_ssdp_already_configured(hass: HomeAssistantType, fritz: Mock):
    """Test starting a flow from discovery when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    assert result["type"] == "create_entry"
    assert not result["result"].unique_id

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "ssdp"}, data=MOCK_SSDP_DATA
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
    assert result["result"].unique_id == "only-a-test"
