"""Test the Overseerr config flow."""
from unittest.mock import Mock

from overseerr_api.exceptions import OpenApiException
import pytest
from urllib3 import HTTPConnectionPool
from urllib3.exceptions import MaxRetryError

from homeassistant import config_entries
from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_validate_input")

USER_INPUT = {CONF_URL: "http://localhost:5055/api/v1", CONF_API_KEY: "test-api-key"}


async def test_form_create_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test flow with no errors
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Overseerr"
    assert result["data"] == {
        CONF_URL: USER_INPUT[CONF_URL],
        CONF_API_KEY: USER_INPUT[CONF_API_KEY],
    }


async def test_form_with_max_retry_exception(
    hass: HomeAssistant,
    mock_validate_input: Mock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Create dummy pool for exception
    pool = HTTPConnectionPool(host="localhost", port=5055)

    # Set MaxRetryError to simulate a connection error
    mock_validate_input.side_effect = MaxRetryError(pool, "Dummy exception")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "open_api_exception"}


async def test_form_with_overseeerr_api_exception(
    hass: HomeAssistant,
    mock_validate_input: Mock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Set OpenApiException to simulate a connection error
    mock_validate_input.side_effect = OpenApiException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "open_api_exception"}


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
