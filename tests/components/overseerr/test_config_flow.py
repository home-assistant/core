"""Test the Overseerr config flow."""
from unittest.mock import patch

from overseerr_api.exceptions import OpenApiException
import pytest
from urllib3 import HTTPConnectionPool
from urllib3.exceptions import MaxRetryError

from homeassistant import config_entries
from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {CONF_URL: "http://localhost:5055/api/v1", CONF_API_KEY: "test-api-key"}


async def test_form_create_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test flow with no errors
    with patch(
        "homeassistant.components.overseerr.config_flow.AuthApi.auth_me_get",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Overseerr"
    assert result["data"] == {
        CONF_URL: USER_INPUT[CONF_URL],
        CONF_API_KEY: USER_INPUT[CONF_API_KEY],
    }


@pytest.mark.parametrize(
    ("exception", "error_string"),
    [
        (OpenApiException, "open_api_exception"),
        (MaxRetryError, "open_api_exception"),
        (Exception, "unknown"),
    ],
)
async def test_form_retries_on_exception(
    hass: HomeAssistant,
    exception: Exception,
    error_string: str,
) -> None:
    """Test that config flow can recover for all expected exceptions."""
    if exception == MaxRetryError:
        pool = HTTPConnectionPool(host="localhost", port=5055)
        exception = MaxRetryError(pool, "Dummy exception")
    with patch(
        "homeassistant.components.overseerr.config_flow.AuthApi.auth_me_get",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=USER_INPUT,
        )

    # Assert that the exception causes error in the form
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_string}

    # Assert that this can be recovered
    with patch(
        "homeassistant.components.overseerr.config_flow.AuthApi.auth_me_get",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Overseerr"
    assert result["data"] == {
        CONF_URL: USER_INPUT[CONF_URL],
        CONF_API_KEY: USER_INPUT[CONF_API_KEY],
    }


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test flow with duplicate config
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
