"""Tests for AVM Fritz!Box config flow."""
import dataclasses
from unittest import mock
from unittest.mock import Mock, patch
from urllib.parse import urlparse

from pyfritzhome import LoginError
import pytest
from requests.exceptions import HTTPError

from homeassistant.components import ssdp
from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.components.ssdp import ATTR_UPNP_FRIENDLY_NAME, ATTR_UPNP_UDN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import MockConfigEntry

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
MOCK_SSDP_DATA = {
    "ip4_valid": ssdp.SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="https://10.0.0.1:12345/test",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: CONF_FAKE_NAME,
            ATTR_UPNP_UDN: "uuid:only-a-test",
        },
    ),
    "ip6_valid": ssdp.SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="https://[1234::1]:12345/test",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: CONF_FAKE_NAME,
            ATTR_UPNP_UDN: "uuid:only-a-test",
        },
    ),
    "ip6_invalid": ssdp.SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="https://[fe80::1%1]:12345/test",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: CONF_FAKE_NAME,
            ATTR_UPNP_UDN: "uuid:only-a-test",
        },
    ),
}


@pytest.fixture(name="fritz")
def fritz_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.fritzbox.async_setup_entry"), patch(
        "homeassistant.components.fritzbox.config_flow.Fritzhome"
    ) as fritz:
        yield fritz


async def test_user(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_DATA
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.0.0.1"
    assert result["data"][CONF_HOST] == "10.0.0.1"
    assert result["data"][CONF_PASSWORD] == "fake_pass"
    assert result["data"][CONF_USERNAME] == "fake_user"
    assert not result["result"].unique_id


async def test_user_auth_failed(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow by user with authentication failure."""
    fritz().login.side_effect = [LoginError("Boom"), mock.DEFAULT]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_not_successful(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow by user but no connection found."""
    fritz().login.side_effect = OSError("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_already_configured(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow by user when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert not result["result"].unique_id

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass: HomeAssistant, fritz: Mock):
    """Test starting a reauthentication flow."""
    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
        data=mock_config.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "other_fake_user",
            CONF_PASSWORD: "other_fake_password",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config.data[CONF_USERNAME] == "other_fake_user"
    assert mock_config.data[CONF_PASSWORD] == "other_fake_password"


async def test_reauth_auth_failed(hass: HomeAssistant, fritz: Mock):
    """Test starting a reauthentication flow with authentication failure."""
    fritz().login.side_effect = LoginError("Boom")

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
        data=mock_config.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "other_fake_user",
            CONF_PASSWORD: "other_fake_password",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_not_successful(hass: HomeAssistant, fritz: Mock):
    """Test starting a reauthentication flow but no connection found."""
    fritz().login.side_effect = OSError("Boom")

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
        data=mock_config.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "other_fake_user",
            CONF_PASSWORD: "other_fake_password",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    "test_data,expected_result",
    [
        (MOCK_SSDP_DATA["ip4_valid"], FlowResultType.FORM),
        (MOCK_SSDP_DATA["ip6_valid"], FlowResultType.FORM),
        (MOCK_SSDP_DATA["ip6_invalid"], FlowResultType.ABORT),
    ],
)
async def test_ssdp(
    hass: HomeAssistant,
    fritz: Mock,
    test_data: ssdp.SsdpServiceInfo,
    expected_result: str,
):
    """Test starting a flow from discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=test_data
    )
    assert result["type"] == expected_result

    if expected_result == FlowResultType.ABORT:
        return

    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "fake_pass", CONF_USERNAME: "fake_user"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == CONF_FAKE_NAME
    assert result["data"][CONF_HOST] == urlparse(test_data.ssdp_location).hostname
    assert result["data"][CONF_PASSWORD] == "fake_pass"
    assert result["data"][CONF_USERNAME] == "fake_user"
    assert result["result"].unique_id == "only-a-test"


async def test_ssdp_no_friendly_name(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow from discovery without friendly name."""
    MOCK_NO_NAME = dataclasses.replace(MOCK_SSDP_DATA["ip4_valid"])
    MOCK_NO_NAME.upnp = MOCK_NO_NAME.upnp.copy()
    del MOCK_NO_NAME.upnp[ATTR_UPNP_FRIENDLY_NAME]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_NO_NAME
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "fake_pass", CONF_USERNAME: "fake_user"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.0.0.1"
    assert result["data"][CONF_HOST] == "10.0.0.1"
    assert result["data"][CONF_PASSWORD] == "fake_pass"
    assert result["data"][CONF_USERNAME] == "fake_user"
    assert result["result"].unique_id == "only-a-test"


async def test_ssdp_auth_failed(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow from discovery with authentication failure."""
    fritz().login.side_effect = LoginError("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA["ip4_valid"]
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "whatever", CONF_USERNAME: "whatever"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"]["base"] == "invalid_auth"


async def test_ssdp_not_successful(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow from discovery but no device found."""
    fritz().login.side_effect = OSError("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA["ip4_valid"]
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "whatever", CONF_USERNAME: "whatever"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_ssdp_not_supported(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow from discovery with unsupported device."""
    fritz().get_device_elements.side_effect = HTTPError("Boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA["ip4_valid"]
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "whatever", CONF_USERNAME: "whatever"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_ssdp_already_in_progress_unique_id(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow from discovery twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA["ip4_valid"]
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA["ip4_valid"]
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_ssdp_already_in_progress_host(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow from discovery twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA["ip4_valid"]
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    MOCK_NO_UNIQUE_ID = dataclasses.replace(MOCK_SSDP_DATA["ip4_valid"])
    MOCK_NO_UNIQUE_ID.upnp = MOCK_NO_UNIQUE_ID.upnp.copy()
    del MOCK_NO_UNIQUE_ID.upnp[ATTR_UPNP_UDN]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_NO_UNIQUE_ID
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_ssdp_already_configured(hass: HomeAssistant, fritz: Mock):
    """Test starting a flow from discovery when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_USER_DATA
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert not result["result"].unique_id

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA["ip4_valid"]
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert result["result"].unique_id == "only-a-test"
