"""Tests for Arris TG2492LG config flow."""

from aiohttp import ClientError

from homeassistant.components.arris_tg2492lg.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG, MOCK_HOST, MOCK_PASSWORD


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry, mock_connect_box
) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Arris TG2492LG ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry, mock_connect_box
) -> None:
    """Test config flow when connection fails."""
    mock_connect_box.return_value.async_login.side_effect = ClientError("fail")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    user_input = {CONF_HOST: MOCK_HOST, CONF_PASSWORD: MOCK_PASSWORD}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_connect_box.return_value.async_login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_entry_exists(
    hass: HomeAssistant, mock_setup_entry, mock_connect_box, mock_config_entry
) -> None:
    """Test where an entry already exists and we try to set it up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, mock_setup_entry, mock_connect_box
) -> None:
    """Test import initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: MOCK_HOST, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Arris TG2492LG ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG


async def test_import_flow_entry_exists(
    hass: HomeAssistant, mock_setup_entry, mock_connect_box, mock_config_entry
) -> None:
    """Test import flow aborts when entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry, mock_connect_box
) -> None:
    """Test import config flow when connection fails."""
    mock_connect_box.return_value.async_login.side_effect = ClientError("fail")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: MOCK_HOST, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
