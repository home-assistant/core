"""Test the smarty config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.smarty.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_smarty: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.2"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.0.2"
    assert result["data"] == {CONF_HOST: "192.168.0.2"}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_cannot_connect(
    hass: HomeAssistant, mock_smarty: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""

    mock_smarty.update.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.2"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_smarty.update.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.2"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_unknown_error(
    hass: HomeAssistant, mock_smarty: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle unknown error."""

    mock_smarty.update.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.2"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_smarty.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.2"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle existing entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, mock_smarty: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the import flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.0.2", CONF_NAME: "Smarty"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Smarty"
    assert result["data"] == {CONF_HOST: "192.168.0.2"}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect(
    hass: HomeAssistant, mock_smarty: AsyncMock
) -> None:
    """Test we handle cannot connect error."""

    mock_smarty.update.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.0.2", CONF_NAME: "Smarty"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_unknown_error(
    hass: HomeAssistant, mock_smarty: AsyncMock
) -> None:
    """Test we handle unknown error."""

    mock_smarty.update.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.0.2", CONF_NAME: "Smarty"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
