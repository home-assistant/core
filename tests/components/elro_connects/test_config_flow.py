"""Test the Elro Connects config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.elro_connects.config_flow import CannotConnect
from homeassistant.components.elro_connects.const import (
    CONF_CONNECTOR_ID,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.elro_connects.config_flow.K1ConnectionTest.async_try_connection",
        return_value=True,
    ), patch(
        "homeassistant.components.elro_connects.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "connector_id": "ST_deadbeef0000",
                "port": 1025,
                "interval": 15,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Elro Connects K1 Connector"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_CONNECTOR_ID: "ST_deadbeef0000",
        CONF_PORT: 1025,
        CONF_UPDATE_INTERVAL: 15,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.elro_connects.config_flow.K1ConnectionTest.async_try_connection",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_CONNECTOR_ID: "ST_deadbeef0000",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_already_setup(hass: HomeAssistant) -> None:
    """Test we cannot create a duplicate setup."""
    # Setup the existing config entry
    await test_form(hass)

    # Now assert the entry creation is aborted if we try
    # to create an entry with the same unique device_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.elro_connects.config_flow.K1ConnectionTest.async_try_connection",
        return_value=True,
    ), patch(
        "homeassistant.components.elro_connects.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.2",
                CONF_CONNECTOR_ID: "ST_deadbeef0000",
                CONF_PORT: 1024,
                CONF_UPDATE_INTERVAL: 10,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT


async def test_update_options(hass: HomeAssistant) -> None:
    """Test we can update the configuration."""
    # Setup the existing config entry
    await test_form(hass)

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    # Start config flow

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Change interval, IP address and port
    with patch(
        "homeassistant.components.elro_connects.config_flow.K1ConnectionTest.async_try_connection",
        return_value=True,
    ), patch(
        "homeassistant.components.elro_connects.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.1.1.2",
                CONF_PORT: 1024,
                CONF_UPDATE_INTERVAL: 10,
            },
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY

    assert config_entry.data.get(CONF_HOST) == "1.1.1.2"
    assert config_entry.data.get(CONF_CONNECTOR_ID) == "ST_deadbeef0000"
    assert config_entry.data.get(CONF_PORT) == 1024
    assert config_entry.data.get(CONF_UPDATE_INTERVAL) == 10
