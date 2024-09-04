"""Test the Russound RIO config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.russound_rio.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG, MOCK_CONTROLLERS, MODEL


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_russound.connect.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover with correct information
    mock_russound.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_no_primary_controller(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound: AsyncMock
) -> None:
    """Test we handle no primary controller error."""
    mock_russound.enumerate_controllers.return_value = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = MOCK_CONFIG
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_primary_controller"}

    # Recover with correct information
    mock_russound.enumerate_controllers.return_value = MOCK_CONTROLLERS
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound: AsyncMock
) -> None:
    """Test we import a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect(
    hass: HomeAssistant, mock_russound: AsyncMock
) -> None:
    """Test we handle import cannot connect error."""
    mock_russound.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_no_primary_controller(
    hass: HomeAssistant, mock_russound: AsyncMock
) -> None:
    """Test import with no primary controller error."""
    mock_russound.enumerate_controllers.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_primary_controller"
