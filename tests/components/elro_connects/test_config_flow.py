"""Test the Elro Connects config flow."""
from unittest.mock import AsyncMock, patch

from elro.api import K1
import pytest

from homeassistant import config_entries
from homeassistant.components.elro_connects.const import CONF_CONNECTOR_ID, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.setup import async_setup_component


async def test_form(hass: HomeAssistant, mock_k1_api: dict[AsyncMock]) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.elro_connects.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "connector_id": "ST_deadbeef0000",
                "port": 1025,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Elro Connects K1 Connector"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_CONNECTOR_ID: "ST_deadbeef0000",
        CONF_PORT: 1025,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "side_effect, error",
    [
        (K1.K1ConnectionError, "cannot_connect"),
        (Exception("Some unhandled error"), "unknown"),
    ],
)
async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_k1_api: dict[AsyncMock],
    side_effect: Exception,
    error: str,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_k1_api["connect"].side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_CONNECTOR_ID: "ST_deadbeef0000",
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": error}


async def test_already_setup(hass: HomeAssistant, mock_k1_api: dict[AsyncMock]) -> None:
    """Test we cannot create a duplicate setup."""
    # Setup the existing unique config entry
    await test_form(hass, mock_k1_api)

    # Now assert the entry creation is aborted if we try
    # to create an entry with the same unique device_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.elro_connects.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.2",
                CONF_CONNECTOR_ID: "ST_deadbeef0000",
                CONF_PORT: 1024,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT


async def test_update_options(
    hass: HomeAssistant,
    mock_k1_connector: dict[AsyncMock],
    mock_k1_api: dict[AsyncMock],
    mock_entry: ConfigEntry,
) -> None:
    """Test we can update the configuration."""
    # Setup the existing config entry
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    # Start config flow

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Change interval, IP address and port
    with patch(
        "homeassistant.components.elro_connects.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.1.1.2",
                CONF_PORT: 1024,
            },
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY

    assert config_entry.data.get(CONF_HOST) == "1.1.1.2"
    assert config_entry.data.get(CONF_CONNECTOR_ID) == "ST_deadbeef0000"
    assert config_entry.data.get(CONF_PORT) == 1024


@pytest.mark.parametrize(
    "side_effect",
    [
        (K1.K1ConnectionError,),
        (Exception("Some unhandled error"),),
    ],
)
async def test_update_options_cannot_connect_handling(
    hass: HomeAssistant, mock_k1_api: dict[AsyncMock], side_effect: Exception
) -> None:
    """Test cannot connect when updating the configuration."""
    # Setup the existing config entry
    await test_form(hass, mock_k1_api)

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    # Start config flow

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Change interval, IP address and port
    mock_k1_api["connect"].side_effect = side_effect
    with patch(
        "homeassistant.components.elro_connects.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.1.1.2",
                CONF_PORT: 1024,
            },
        )
    assert result["type"] == RESULT_TYPE_FORM
