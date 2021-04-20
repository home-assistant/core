"""Tests for AVM Fritz!Box config flow."""
from unittest.mock import patch

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
import pytest

from homeassistant.components.fritz import config_flow
from homeassistant.components.fritz.const import ATTR_HOST, DOMAIN
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import MOCK_CONFIG, FritzConnectionMock

from tests.common import MockConfigEntry

ATTR_NEW_SERIAL_NUMBER = "NewSerialNumber"

MOCK_HOST = "fake_host"
MOCK_SERIAL_NUMBER = "fake_serial_number"


MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
MOCK_DEVICE_INFO = {
    ATTR_HOST: MOCK_HOST,
    ATTR_NEW_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
}
MOCK_IMPORT_CONFIG = {CONF_HOST: "yaml_host"}
MOCK_SSDP_DATA = {
    ATTR_SSDP_LOCATION: "https://fake_host:12345/test",
    ATTR_UPNP_FRIENDLY_NAME: "fake_name",
    ATTR_UPNP_UDN: "uuid:only-a-test",
}


@pytest.fixture()
def fc_class_mock(mocker):
    """Fixture that sets up a mocked FritzConnection class."""
    result = mocker.patch("fritzconnection.FritzConnection", autospec=True)
    result.return_value = FritzConnectionMock()
    yield result


async def test_user(hass: HomeAssistantType, fc_class_mock):
    """Test starting a flow by user."""
    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "start_config"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_PASSWORD] == "fake_pass"
        assert result["data"][CONF_USERNAME] == "fake_user"
        assert not result["result"].unique_id


async def test_user_already_configured(hass: HomeAssistantType, fc_class_mock):
    """Test starting a flow by user."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "start_config"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "start_config"


async def test_exception_security(hass: HomeAssistantType):
    """Test starting a flow by user."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "start_config"

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=FritzSecurityError,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "start_config"
        assert result["errors"]["base"] == "invalid_auth"


async def test_exception_connection(hass: HomeAssistantType):
    """Test starting a flow by user."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "start_config"

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=FritzConnectionException,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "start_config"
        assert result["errors"]["base"] == "connection_error"


async def test_reauth_successful(hass: HomeAssistantType, fc_class_mock):
    """Test starting a reauthentication flow but no connection found."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
            data=mock_config.data,
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "other_fake_user",
                CONF_PASSWORD: "other_fake_password",
            },
        )

        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"


async def test_reauth_not_successful(hass: HomeAssistantType, fc_class_mock):
    """Test starting a reauthentication flow but no connection found."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=FritzConnectionException,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
            data=mock_config.data,
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "other_fake_user",
                CONF_PASSWORD: "other_fake_password",
            },
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "reauth_confirm"


async def test_ssdp_already_configured(hass: HomeAssistantType, fc_class_mock):
    """Test starting a flow from discovery but no device found."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id="only-a-test",
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_ssdp_already_configured_host(hass: HomeAssistantType, fc_class_mock):
    """Test starting a flow from discovery but no device found."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id="different-test",
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_ssdp_already_configured_host_uuid(
    hass: HomeAssistantType, fc_class_mock
):
    """Test starting a flow from discovery but no device found."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=None,
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_ssdp_already_in_progress_host(hass: HomeAssistantType, fc_class_mock):
    """Test starting a flow from discovery twice."""
    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "confirm"

        MOCK_NO_UNIQUE_ID = MOCK_SSDP_DATA.copy()
        del MOCK_NO_UNIQUE_ID[ATTR_UPNP_UDN]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_NO_UNIQUE_ID
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_in_progress"


async def test_ssdp(hass: HomeAssistantType, fc_class_mock):
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "fake_user",
                CONF_PASSWORD: "fake_pass",
            },
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_PASSWORD] == "fake_pass"
        assert result["data"][CONF_USERNAME] == "fake_user"


async def test_ssdp_exception(hass: HomeAssistantType):
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=FritzConnectionException,
    ), patch("homeassistant.components.fritz.common.FritzStatus"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "fake_user",
                CONF_PASSWORD: "fake_pass",
            },
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "confirm"


async def test_import(hass: HomeAssistantType):
    """Test importing."""

    flow = config_flow.FritzBoxToolsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(MOCK_IMPORT_CONFIG)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "start_config"
