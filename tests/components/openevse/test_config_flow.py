"""Tests for the OpenEVSE sensor platform."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow create entry with bad charger."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }


async def test_user_flow_flaky(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow create entry with flaky charger."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    mock_charger.update.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "cannot_connect"}

    mock_charger.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow aborts when config entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
    }


async def test_import_flow_bad(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow with bad charger."""
    mock_charger.update.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unavailable_host"


async def test_import_flow_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow aborts when config entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.1.100"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
