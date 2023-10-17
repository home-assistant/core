"""Test the MyPermobil config flow."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.permobil import config_flow
from homeassistant.components.permobil.const import DOMAIN
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_REGION, CONF_TOKEN, CONF_TTL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_URL = "https://example.com"
MOCK_REGION = "region_name"
MOCK_REGIONS = {MOCK_REGION: MOCK_URL}
MOCK_TOKEN = ("a" * 256, "date")
MOCK_CODE = "012345"
MOCK_EMAIL = "valid@email.com"
EMPTY = ""
INVALID_EMAIL = "this is not a valid email"
INVALID_REGION = "this is not a valid region"
INVALID_CODE = "this is not a valid code"
MOCK_REENTRY = MagicMock()
MOCK_REENTRY.data = {CONF_EMAIL: MOCK_EMAIL, CONF_REGION: MOCK_URL}
MOCK_CONTEXT = {"entry_id": None}


class MockApiClientError:
    """An instance of the api that always returns an client exception when called."""

    def set_email(self):
        """Raise exception."""
        raise config_flow.MyPermobilClientException

    def set_code(self):
        """Raise exception."""
        raise config_flow.MyPermobilClientException


class MockApiAPIError:
    """An instance of the api that always returns an API exception when called."""

    region = ""

    def set_region(self):
        """Pass."""

    def set_code(self):
        """Pass."""

    async def request_application_code():
        """Raise MyPermobilAPIException."""
        raise config_flow.MyPermobilAPIException

    async def request_region_names():
        """Raise MyPermobilAPIException."""
        raise config_flow.MyPermobilAPIException

    async def request_application_token():
        """Raise MyPermobilAPIException."""
        raise config_flow.MyPermobilAPIException


class MockApiSuccess:
    """An instance of the api that never complains."""

    region = ""

    def set_region(self):
        """Pass."""

    def set_code(self):
        """Pass."""

    async def request_application_code():
        """Fake a request for application code."""

    async def request_application_token():
        """Return a mock token."""
        return MOCK_TOKEN


async def test_flow_init(hass: HomeAssistant) -> None:
    """Test config flow init."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_invalid_region_api(hass: HomeAssistant) -> None:
    """Test we handle invalid region."""
    with patch(
        "homeassistant.components.permobil.config_flow.PermobilConfigFlow.p_api",
        MockApiAPIError,
    ), patch(
        "homeassistant.components.permobil.config_flow.PermobilConfigFlow.region_names",
        MOCK_REGIONS,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "region"},
            data={CONF_REGION: MOCK_REGION},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"].get("base") == "region_connection_error"


async def test_form_invalid_email(hass: HomeAssistant) -> None:
    """Test we handle invalid email."""
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil",
        lambda x, session: MockApiClientError,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: INVALID_EMAIL},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"].get("base") == "invalid_email"


async def test_form_invalid_code(hass: HomeAssistant) -> None:
    """Test we handle invalid code."""
    with patch(
        "homeassistant.components.permobil.config_flow.PermobilConfigFlow.p_api",
        MockApiClientError,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "email_code"},
            data={CONF_CODE: INVALID_CODE},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"].get("base") == "invalid_code"


async def test_form_valid_email(hass: HomeAssistant) -> None:
    """Test we handle a valid email."""
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil.request_region_names",
        return_value=MOCK_REGIONS,
    ) as mock:
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: MOCK_EMAIL},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"] == {}
    assert len(mock.mock_calls) == 1
    assert config_flow.PermobilConfigFlow.data.get(CONF_EMAIL) == MOCK_EMAIL


async def test_form_valid_region(hass: HomeAssistant) -> None:
    """Test we handle a valid region."""
    with patch(
        "homeassistant.components.permobil.config_flow.PermobilConfigFlow.p_api",
        MockApiSuccess,
    ), patch(
        "homeassistant.components.permobil.config_flow.PermobilConfigFlow.region_names",
        MOCK_REGIONS,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "region"},
            data={CONF_REGION: MOCK_REGION},
        )

    expected_region = MOCK_REGIONS.get(MOCK_REGION)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data.get(CONF_REGION) == expected_region


async def test_form_valid_code(hass: HomeAssistant) -> None:
    """Test we handle a valid email."""
    with patch(
        "homeassistant.components.permobil.config_flow.PermobilConfigFlow.p_api",
        MockApiSuccess,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "email_code"},
            data={CONF_CODE: MOCK_CODE},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"].get(CONF_CODE) == MOCK_CODE
    assert result["data"].get(CONF_TOKEN) == MOCK_TOKEN[0]
    assert result["data"].get(CONF_TTL) == MOCK_TOKEN[1]
    assert not result.get("errors")


async def test_form_connection_error_region(hass: HomeAssistant) -> None:
    """Test we handle a connection error."""
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil.request_region_names",
        side_effect=config_flow.MyPermobilAPIException,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "user"},
            data={CONF_EMAIL: MOCK_EMAIL},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "region"
    assert result["errors"].get("base") == "region_fetch_error"


async def test_form_connection_error_token(hass: HomeAssistant) -> None:
    """Test we handle a connection error."""
    with patch(
        "homeassistant.components.permobil.config_flow.PermobilConfigFlow.p_api",
        MockApiAPIError,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "email_code"},
            data={CONF_CODE: MOCK_CODE},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"].get("base") == "invalid_code"


async def test_form_reauth_api_fail(hass: HomeAssistant) -> None:
    """Test we handle a connection error. in the reauth flow."""
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil.request_application_code",
        side_effect=config_flow.MyPermobilAPIException,
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_get_entry",
        return_value=MOCK_REENTRY,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth"
    assert result["errors"].get("base") == "region_connection_error"


async def test_form_reauth_context_fail(hass: HomeAssistant) -> None:
    """Test we handle a connection error. in the reauth flow."""
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil.request_application_code",
        side_effect=config_flow.MyPermobilAPIException,
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_get_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth"
    assert result["errors"].get("base") == "unknown"


async def test_form_reauth_api_success(hass: HomeAssistant) -> None:
    """Test we handle a reauth."""
    with patch(
        "homeassistant.components.permobil.config_flow.MyPermobil.request_application_code",
        return_value=True,
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_get_entry",
        return_value=MOCK_REENTRY,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "reauth"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "email_code"
    assert result["errors"] == {}
    assert config_flow.PermobilConfigFlow.data.get(CONF_REGION) == MOCK_URL
    assert config_flow.PermobilConfigFlow.data.get(CONF_EMAIL) == MOCK_EMAIL
