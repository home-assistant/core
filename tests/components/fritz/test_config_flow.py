"""Tests for Fritz!Tools config flow."""
import dataclasses
from unittest.mock import patch

from fritzconnection.core.exceptions import (
    FritzAuthorizationError,
    FritzConnectionException,
    FritzSecurityError,
)
import pytest

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.components.fritz.const import (
    DOMAIN,
    ERROR_AUTH_INVALID,
    ERROR_CANNOT_CONNECT,
    ERROR_UNKNOWN,
    FRITZ_AUTH_EXCEPTIONS,
)
from homeassistant.components.ssdp import ATTR_UPNP_UDN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    MOCK_FIRMWARE_INFO,
    MOCK_IPS,
    MOCK_REQUEST,
    MOCK_SSDP_DATA,
    MOCK_USER_DATA,
)

from tests.common import MockConfigEntry


async def test_user(hass: HomeAssistant, fc_class_mock, mock_get_source_ip) -> None:
    """Test starting a flow by user."""
    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch(
        "homeassistant.components.fritz.common.FritzBoxTools._update_device_info",
        return_value=MOCK_FIRMWARE_INFO,
    ), patch(
        "homeassistant.components.fritz.async_setup_entry"
    ) as mock_setup_entry, patch(
        "requests.get"
    ) as mock_request_get, patch(
        "requests.post"
    ) as mock_request_post, patch(
        "homeassistant.components.fritz.config_flow.socket.gethostbyname",
        return_value=MOCK_IPS["fritz.box"],
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_PASSWORD] == "fake_pass"
        assert result["data"][CONF_USERNAME] == "fake_user"
        assert (
            result["options"][CONF_CONSIDER_HOME]
            == DEFAULT_CONSIDER_HOME.total_seconds()
        )
        assert not result["result"].unique_id
        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_user_already_configured(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip
) -> None:
    """Test starting a flow by user with an already configured device."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch(
        "homeassistant.components.fritz.common.FritzBoxTools._update_device_info",
        return_value=MOCK_FIRMWARE_INFO,
    ), patch(
        "requests.get"
    ) as mock_request_get, patch(
        "requests.post"
    ) as mock_request_post, patch(
        "homeassistant.components.fritz.config_flow.socket.gethostbyname",
        return_value=MOCK_IPS["fritz.box"],
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "already_configured"


@pytest.mark.parametrize(
    "error",
    FRITZ_AUTH_EXCEPTIONS,
)
async def test_exception_security(
    hass: HomeAssistant, mock_get_source_ip, error
) -> None:
    """Test starting a flow by user with invalid credentials."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == ERROR_AUTH_INVALID


async def test_exception_connection(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=FritzConnectionException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == ERROR_CANNOT_CONNECT


async def test_exception_unknown(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test starting a flow by user with an unknown exception."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == ERROR_UNKNOWN


async def test_reauth_successful(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip
) -> None:
    """Test starting a reauthentication flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch(
        "homeassistant.components.fritz.common.FritzBoxTools._update_device_info",
        return_value=MOCK_FIRMWARE_INFO,
    ), patch(
        "homeassistant.components.fritz.async_setup_entry"
    ) as mock_setup_entry, patch(
        "requests.get"
    ) as mock_request_get, patch(
        "requests.post"
    ) as mock_request_post:
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

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

    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (FritzAuthorizationError, ERROR_AUTH_INVALID),
        (FritzConnectionException, ERROR_CANNOT_CONNECT),
        (FritzSecurityError, ERROR_AUTH_INVALID),
    ],
)
async def test_reauth_not_successful(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip, side_effect, error
) -> None:
    """Test starting a reauthentication flow but no connection found."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=side_effect,
    ):
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
        assert result["errors"]["base"] == error


async def test_ssdp_already_configured(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip
) -> None:
    """Test starting a flow from discovery with an already configured device."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id="only-a-test",
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch(
        "homeassistant.components.fritz.config_flow.socket.gethostbyname",
        return_value=MOCK_IPS["fritz.box"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_ssdp_already_configured_host(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip
) -> None:
    """Test starting a flow from discovery with an already configured host."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id="different-test",
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch(
        "homeassistant.components.fritz.config_flow.socket.gethostbyname",
        return_value=MOCK_IPS["fritz.box"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_ssdp_already_configured_host_uuid(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip
) -> None:
    """Test starting a flow from discovery with an already configured uuid."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=None,
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch(
        "homeassistant.components.fritz.config_flow.socket.gethostbyname",
        return_value=MOCK_IPS["fritz.box"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_ssdp_already_in_progress_host(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip
) -> None:
    """Test starting a flow from discovery twice."""
    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        MOCK_NO_UNIQUE_ID = dataclasses.replace(MOCK_SSDP_DATA)
        MOCK_NO_UNIQUE_ID.upnp = MOCK_NO_UNIQUE_ID.upnp.copy()
        del MOCK_NO_UNIQUE_ID.upnp[ATTR_UPNP_UDN]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_NO_UNIQUE_ID
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_in_progress"


async def test_ssdp(hass: HomeAssistant, fc_class_mock, mock_get_source_ip) -> None:
    """Test starting a flow from discovery."""
    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch(
        "homeassistant.components.fritz.common.FritzBoxTools._update_device_info",
        return_value=MOCK_FIRMWARE_INFO,
    ), patch(
        "homeassistant.components.fritz.async_setup_entry"
    ) as mock_setup_entry, patch(
        "requests.get"
    ) as mock_request_get, patch(
        "requests.post"
    ) as mock_request_post:
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "fake_user",
                CONF_PASSWORD: "fake_pass",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == MOCK_IPS["fritz.box"]
        assert result["data"][CONF_PASSWORD] == "fake_pass"
        assert result["data"][CONF_USERNAME] == "fake_user"

    assert mock_setup_entry.called


async def test_ssdp_exception(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test starting a flow from discovery but no device found."""
    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=FritzConnectionException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "fake_user",
                CONF_PASSWORD: "fake_pass",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"


async def test_options_flow(
    hass: HomeAssistant, fc_class_mock, mock_get_source_ip
) -> None:
    """Test options flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzBoxTools"):
        result = await hass.config_entries.options.async_init(mock_config.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_init(mock_config.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONSIDER_HOME: 37,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert mock_config.options[CONF_CONSIDER_HOME] == 37
