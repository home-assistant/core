"""Test the MyPermobil config flow."""
from unittest.mock import AsyncMock, Mock, patch

from mypermobil import MyPermobilAPIException, MyPermobilClientException
import pytest

from homeassistant import config_entries
from homeassistant.components.permobil import config_flow
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_REGION, CONF_TOKEN, CONF_TTL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_URL = "https://example.com"
MOCK_REGION_NAME = "region_name"
MOCK_REGIONS = {MOCK_REGION_NAME: MOCK_URL}
MOCK_TOKEN = ("a" * 256, "date")
MOCK_CODE = "012345"
MOCK_EMAIL = "valid@email.com"
INVALID_EMAIL = "this is not a valid email"


async def test_sucessful_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow from start to finish with no errors."""
    mock_api: Mock = Mock()
    mock_api.request_region_names = AsyncMock(return_value=MOCK_REGIONS)
    mock_api.request_application_code = AsyncMock(return_value=None)
    mock_api.request_application_token = AsyncMock(return_value=MOCK_TOKEN)

    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data[CONF_EMAIL] == MOCK_EMAIL

    # select region step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data[CONF_REGION] == MOCK_URL

    # request region code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: MOCK_CODE},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CODE] == MOCK_CODE
    assert result["data"][CONF_TOKEN] == MOCK_TOKEN[0]
    assert result["data"][CONF_TTL] == MOCK_TOKEN[1]

    # test the reauth
    reauth_entry = hass.config_entries.async_entries(config_flow.DOMAIN)[0]
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth", "entry_id": reauth_entry.entry_id},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data.get(CONF_REGION) == MOCK_URL
    assert config_flow.PermobilConfigFlow.data.get(CONF_EMAIL) == MOCK_EMAIL


async def test_sucessful_config_flow_fail_reauth(hass: HomeAssistant) -> None:
    """Test the config flow from start to finish with no errors."""
    mock_api: Mock = Mock()
    mock_api.request_region_names = AsyncMock(return_value=MOCK_REGIONS)
    mock_api.request_application_code = AsyncMock(return_value=None)
    mock_api.request_application_token = AsyncMock(return_value=MOCK_TOKEN)
    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data[CONF_EMAIL] == MOCK_EMAIL

    # select region step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data[CONF_REGION] == MOCK_URL

    # request region code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: MOCK_CODE},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CODE] == MOCK_CODE
    assert result["data"][CONF_TOKEN] == MOCK_TOKEN[0]
    assert result["data"][CONF_TTL] == MOCK_TOKEN[1]

    # test the reauth and have request_application_code fail leading to an abort
    mock_api.request_application_code = AsyncMock(side_effect=MyPermobilAPIException)
    reauth_entry = hass.config_entries.async_entries(config_flow.DOMAIN)[0]
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth", "entry_id": reauth_entry.entry_id},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_config_flow_incorrect_code(hass: HomeAssistant) -> None:
    """Test the config flow from start to until email code verification and have the API return error."""
    mock_api: Mock = Mock()
    mock_api.request_region_names = AsyncMock(return_value=MOCK_REGIONS)
    mock_api.request_application_code = AsyncMock(return_value=None)
    mock_api.request_application_token = AsyncMock(side_effect=MyPermobilAPIException)
    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data[CONF_EMAIL] == MOCK_EMAIL

    # select region step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data[CONF_REGION] == MOCK_URL

    # request region code
    # here the request_application_token raises a MyPermobilAPIException
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: MOCK_CODE},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"]["base"] == "invalid_code"


async def test_config_flow_incorrect_region(hass: HomeAssistant) -> None:
    """Test the config flow from start to until the request for email code and have the API return error."""
    mock_api: Mock = Mock()
    mock_api.request_region_names = AsyncMock(return_value=MOCK_REGIONS)
    mock_api.request_application_code = AsyncMock(side_effect=MyPermobilAPIException)
    mock_api.request_application_token = AsyncMock(return_value=None)
    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data[CONF_EMAIL] == MOCK_EMAIL

    # select region step
    # here the request_application_code raises a MyPermobilAPIException
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"]["base"] == "code_request_error"


async def test_config_flow_region_request_error(hass: HomeAssistant) -> None:
    """Test the config flow from start to until the request for regions and have the API return error."""
    mock_api: Mock = Mock()
    mock_api.request_region_names = AsyncMock(side_effect=MyPermobilAPIException)
    mock_api.request_application_code = AsyncMock(return_value=None)
    mock_api.request_application_token = AsyncMock(return_value=None)
    # init flow
    # here the request_region_names raises a MyPermobilAPIException
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"]["base"] == "region_fetch_error"


async def test_config_flow_invalid_email(hass: HomeAssistant) -> None:
    """Test the config flow from start to until the request for regions and have the API return error."""
    mock_api: Mock = Mock()
    mock_api.set_email: Mock = Mock(side_effect=MyPermobilClientException())
    # init flow
    # here the set_email raises a MyPermobilClientException
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: INVALID_EMAIL},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["errors"]["base"] == "invalid_email"
