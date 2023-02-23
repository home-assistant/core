"""Test the Obihai config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.obihai.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import USER_INPUT


async def test_user_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the user initiated form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch("pyobihai.PyObihai.check_account"), patch(
        "homeassistant.components.obihai.async_setup_entry"
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.10.30"
    assert result["data"] == {**USER_INPUT}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_auth_failure(hass: HomeAssistant) -> None:
    """Test we get the authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.obihai.config_flow.validate_auth", return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["errors"]["base"] == "cannot_connect"


async def test_yaml_import(hass: HomeAssistant) -> None:
    """Test we get the YAML imported."""
    with patch(
        "homeassistant.components.obihai.config_flow.validate_auth", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert "errors" not in result
