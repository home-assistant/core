""""Unit tests for the Lupusec config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.lupusec.config_flow import (
    is_valid_host,
    validate_configuration,
)
from homeassistant.components.lupusec.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form_empty_input(hass: HomeAssistant) -> None:
    """Test handling empty user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "empty_input"}


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test handling invalid host input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "invalid_host",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"host": "invalid_host"}


async def test_form_valid_input(hass: HomeAssistant) -> None:
    """Test handling valid user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.lupusec.config_flow.validate_configuration",
        return_value={},
    ), patch(
        "homeassistant.components.lupusec.config_flow.LupusecConfigFlowHandler.async_create_entry",
        return_value=True,
    ) as mock_create_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "name": "test-device",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "name": "test-device",
    }
    assert len(mock_create_entry.mock_calls) == 1


async def test_validate_configuration_invalid_host() -> None:
    """Test validation of invalid host."""
    errors = await validate_configuration("invalid_host", "user", "password", "name")
    assert errors == {"host": "invalid_host"}


async def test_is_valid_host() -> None:
    """Test is_valid_host function."""
    assert is_valid_host("1.1.1.1")
    assert is_valid_host("example.com")
    assert not is_valid_host("invalid_host")
