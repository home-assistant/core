"""Define tests for the IQVIA config flow."""
from unittest.mock import patch

from pyiqvia.errors import InvalidZipError

from homeassistant import data_entry_flow
from homeassistant.components.iqvia import CONF_ZIP_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from .conftest import TEST_ZIP_CODE


async def test_create_entry(hass: HomeAssistant, config, mock_pyiqvia) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test a bad ZIP code as input:
    with patch(
        "homeassistant.components.iqvia.config_flow.Client", side_effect=InvalidZipError
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {CONF_ZIP_CODE: "invalid_zip_code"}

    # Test that we can recover from the error:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_ZIP_CODE
    assert result["data"] == {CONF_ZIP_CODE: TEST_ZIP_CODE}


async def test_duplicate_error(hass: HomeAssistant, config, setup_config_entry) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
