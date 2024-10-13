"""Test the MyPermobil config flow."""

from unittest.mock import Mock, patch

from mypermobil import (
    MyPermobilAPIException,
    MyPermobilClientException,
    MyPermobilEulaException,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.permobil import config_flow
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_REGION, CONF_TOKEN, CONF_TTL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_REGION_NAME, MOCK_TOKEN, MOCK_URL

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_CODE = "012345"
MOCK_EMAIL = "valid@email.com"
INVALID_EMAIL = "this is not a valid email"
VALID_DATA = {
    CONF_EMAIL: MOCK_EMAIL,
    CONF_REGION: MOCK_URL,
    CONF_CODE: MOCK_CODE,
    CONF_TOKEN: MOCK_TOKEN[0],
    CONF_TTL: MOCK_TOKEN[1],
}


async def test_sucessful_config_flow(hass: HomeAssistant, my_permobil: Mock) -> None:
    """Test the config flow from start to finish with no errors."""
    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}

    # select region step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}
    # request region code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: MOCK_CODE},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == VALID_DATA


async def test_config_flow_incorrect_code(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test email code verification with API error.

    Test the config flow from start to until email code verification
    and have the API return API error.
    """
    my_permobil.request_application_token.side_effect = MyPermobilAPIException
    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}

    # select region step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}

    # request region code
    # here the request_application_token raises a MyPermobilAPIException
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: MOCK_CODE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"]["base"] == "invalid_code"


async def test_config_flow_unsigned_eula(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test email code verification with unsigned eula error.

    Test the config flow from start to until email code verification
    and have the API return that the eula is unsigned.
    """
    my_permobil.request_application_token.side_effect = MyPermobilEulaException
    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}

    # select region step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}

    # request region code
    # here the request_application_token raises a MyPermobilEulaException
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: MOCK_CODE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"]["base"] == "unsigned_eula"

    # Retry to submit the code again, but this time the user has signed the EULA
    with patch.object(
        my_permobil,
        "request_application_token",
        return_value=MOCK_TOKEN,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CODE: MOCK_CODE},
        )

    # Now the method should not raise an exception, and you can proceed with your assertions
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == VALID_DATA


async def test_config_flow_incorrect_region(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test when the user does not exist in the selected region.

    Test the config flow from start to until the request for email
    code and have the API return error because there is not user for
    that email.
    """
    my_permobil.request_application_code.side_effect = MyPermobilAPIException
    # init flow
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}

    # select region step
    # here the request_application_code raises a MyPermobilAPIException
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REGION: MOCK_REGION_NAME},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"]["base"] == "code_request_error"


async def test_config_flow_region_request_error(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test region request error.

    Test the config flow from start to until the request for regions
    and have the API return an error.
    """
    my_permobil.request_region_names.side_effect = MyPermobilAPIException
    # init flow
    # here the request_region_names raises a MyPermobilAPIException
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"]["base"] == "region_fetch_error"


async def test_config_flow_invalid_email(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test an incorrectly formatted email.

    Test that the email must be formatted correctly. The schema for the
    input should already check for this, but since the API does a
    separate check that might not overlap 100% with the schema,
    this test is still needed.
    """
    my_permobil.set_email.side_effect = MyPermobilClientException()
    # init flow
    # here the set_email raises a MyPermobilClientException
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: INVALID_EMAIL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["errors"]["base"] == "invalid_email"


async def test_config_flow_reauth_success(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test the config flow reauth make sure that the values are replaced."""
    # new token and code
    reauth_token = ("b" * 256, "reauth_date")
    reauth_code = "567890"
    my_permobil.request_application_token.return_value = reauth_token

    mock_entry = MockConfigEntry(
        domain="permobil",
        data=VALID_DATA,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth", "entry_id": mock_entry.entry_id},
            data=mock_entry.data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}

    # request new token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: reauth_code},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_EMAIL: MOCK_EMAIL,
        CONF_REGION: MOCK_URL,
        CONF_CODE: reauth_code,
        CONF_TOKEN: reauth_token[0],
        CONF_TTL: reauth_token[1],
    }


async def test_config_flow_reauth_fail_invalid_code(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test the config flow reauth when the email code fails."""
    # new code
    reauth_invalid_code = "567890"  # pretend this code is invalid/incorrect
    my_permobil.request_application_token.side_effect = MyPermobilAPIException
    mock_entry = MockConfigEntry(
        domain="permobil",
        data=VALID_DATA,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth", "entry_id": mock_entry.entry_id},
            data=mock_entry.data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}

    # request request new token but have the API return error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: reauth_invalid_code},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"]["base"] == "invalid_code"


async def test_config_flow_reauth_fail_code_request(
    hass: HomeAssistant, my_permobil: Mock
) -> None:
    """Test the config flow reauth."""
    my_permobil.request_application_code.side_effect = MyPermobilAPIException
    mock_entry = MockConfigEntry(
        domain="permobil",
        data=VALID_DATA,
    )
    mock_entry.add_to_hass(hass)
    # test the reauth and have request_application_code fail leading to an abort
    my_permobil.request_application_code.side_effect = MyPermobilAPIException
    reauth_entry = hass.config_entries.async_entries(config_flow.DOMAIN)[0]
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        return_value=my_permobil,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth", "entry_id": reauth_entry.entry_id},
            data=mock_entry.data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
