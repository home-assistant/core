"""Test the Cybro config flow."""
from unittest.mock import MagicMock

from cybro import CybroConnectionError

from homeassistant.components.cybro.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_full_user_flow_implementation(
    hass: HomeAssistant, mock_cybro_config_flow: MagicMock, mock_setup_entry: None
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.123",
            CONF_PORT: 4000,
            CONF_ADDRESS: 1000,
        },
    )

    assert result.get("title") == "c1000@192.168.1.123:4000"
    assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert result["data"][CONF_PORT] == 4000
    assert result["data"][CONF_ADDRESS] == 1000


async def test_connection_error(
    hass: HomeAssistant, mock_cybro_config_flow: MagicMock
) -> None:
    """Test we show user form on Cybro scgi connection error."""
    mock_cybro_config_flow.update.side_effect = CybroConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "example.com",
            CONF_PORT: 4000,
            CONF_ADDRESS: 1000,
        },
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_server_stopped(
    hass: HomeAssistant,
    mock_cybro_config_flow: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test we show user form on empty Cybro scgi server port answer."""
    mock_cybro_config_flow.update.return_value.server_info.scgi_port_status = ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.123",
            CONF_PORT: 4000,
            CONF_ADDRESS: 1001,
        },
    )

    assert result.get("reason") == "scgi_server_not_running"


async def test_plc_not_existing(
    hass: HomeAssistant,
    mock_cybro_config_flow: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test we show user form on Cybro PLC not existing."""
    mock_cybro_config_flow.update.return_value.plc_info.plc_program_status = ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.123",
            CONF_PORT: 4000,
            CONF_ADDRESS: 1000,
        },
    )

    assert result.get("reason") == "plc_not_existing"
