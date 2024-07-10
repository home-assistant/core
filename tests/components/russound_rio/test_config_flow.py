"""Test the Russound RIO config flow."""

from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.russound_rio.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG, MOCK_DATA, MODEL


async def test_form(hass: HomeAssistant, mock_russound) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.russound_rio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.russound_rio.config_flow.Russound",
            return_value=mock_russound,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == MODEL
    assert result2["data"] == MOCK_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.russound_rio.config_flow.Russound.connect",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] is data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_no_primary_controller(hass: HomeAssistant, mock_russound) -> None:
    """Test we handle no primary controller error."""
    mock_russound.enumerate_controllers.return_value = []
    with patch(
        "homeassistant.components.russound_rio.config_flow.Russound",
        return_value=mock_russound,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

        mock_russound.enumerate_controllers.return_value = []

        user_input = MOCK_CONFIG
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        assert result2["type"] is data_entry_flow.FlowResultType.FORM
        assert result2["errors"] == {"base": "no_primary_controller"}


async def test_import(hass: HomeAssistant, mock_russound) -> None:
    """Test we import a config entry."""
    with (
        patch(
            "homeassistant.components.russound_rio.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.russound_rio.config_flow.Russound",
            return_value=mock_russound,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_CONFIG,
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle import cannot connect error."""

    with patch(
        "homeassistant.components.russound_rio.config_flow.Russound.connect",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_no_primary_controller(hass: HomeAssistant, mock_russound) -> None:
    """Test import with no primary controller error."""
    mock_russound.enumerate_controllers.return_value = []

    with patch(
        "homeassistant.components.russound_rio.config_flow.Russound",
        return_value=mock_russound,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_primary_controller"
