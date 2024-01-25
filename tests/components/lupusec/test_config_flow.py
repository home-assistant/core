""""Unit tests for the Lupusec config flow."""

from unittest.mock import patch

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant import config_entries
from homeassistant.components.lupusec.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form_empty_input(hass: HomeAssistant) -> None:
    """Test handling empty user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    try:
        await hass.config_entries.flow.async_configure(result["flow_id"], {})
        pytest.fail("Expected error not raised")
    except MultipleInvalid as e:
        # Check if the error contains the expected missing key
        assert any(
            "required key not provided @ data['username']" in str(err)
            for err in e.errors
        )


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test handling invalid host input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "invalid_host",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_valid_input(hass: HomeAssistant) -> None:
    """Test handling valid user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lupusec.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "lupupy.Lupusec.__init__",
        return_value=None,
    ) as mock_initialize_lupusec:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_initialize_lupusec.mock_calls) == 1
