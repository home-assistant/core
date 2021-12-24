"""Test the Vallox integration config flow."""
from unittest.mock import patch

from homeassistant.components.vallox.config_flow import CannotConnect, InvalidHost
from homeassistant.components.vallox.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


async def test_form_no_input_fails(hass: HomeAssistant) -> None:
    """Test that the form is returned with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None


async def test_form_create_entry(hass: HomeAssistant) -> None:
    """Test that an entry is created with valid input."""
    name = "Vallox 110 MV"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: name},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"host": "unknown"}

    with patch(
        "homeassistant.components.vallox.config_flow.validate_host",
        return_value={"title": name, "model": "Vallox 110 MV"},
    ), patch(
        "homeassistant.components.vallox.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.2.3.4", "name": name},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == name
    assert result2["data"] == {"host": "1.2.3.4", "name": "Vallox 110 MV"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test that invalid host error is handled."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vallox.config_flow.validate_host",
        side_effect=InvalidHost,
    ):
        result = await hass.config_entries.flow.async_configure(
            init["flow_id"],
            {"host": "10.20.30.40"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"host": "invalid_host"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test that cannot connect error is handled."""
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vallox.config_flow.validate_host",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            init["flow_id"],
            {"host": "4.3.2.1"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"host": "cannot_connect"}


async def test_import(hass: HomeAssistant) -> None:
    """Test that import is handled."""
    name = "Vallox 90 MV"

    with patch(
        "homeassistant.components.vallox.config_flow.validate_host",
        return_value={"title": name, "model": "Vallox 90 MV"},
    ), patch(
        "homeassistant.components.vallox.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"host": "1.2.3.4", "name": name},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == name
    assert result["data"] == {"host": "1.2.3.4", "name": "Vallox 90 MV"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_invalid_host(hass: HomeAssistant) -> None:
    """Test that invalid host error is handled during import."""
    name = "Vallox 90 MV"

    with patch(
        "homeassistant.components.vallox.config_flow.validate_host",
        side_effect=InvalidHost,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"host": "1.2.3.4", "name": name},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "invalid_host"


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test that cannot connect error is handled."""
    name = "Vallox 90 MV"

    with patch(
        "homeassistant.components.vallox.config_flow.validate_host",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"host": "1.2.3.4", "name": name},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"
