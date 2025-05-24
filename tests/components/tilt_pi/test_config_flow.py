"""Test the Tilt config flow."""

from types import MappingProxyType
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_async_step_user_gets_form(hass: HomeAssistant) -> None:
    """Test that we can view the form when there is no previous user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


async def test_async_step_user_creates_entry(
    hass: HomeAssistant,
    mock_config_entry_data: MappingProxyType[str, any],
    mock_tiltpi_client: MagicMock,
) -> None:
    """Test that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "homeassistant.components.tilt_pi.config_flow.TiltPiClient",
        return_value=mock_tiltpi_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=mock_config_entry_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == mock_config_entry_data


async def test_async_step_user_connection_error(
    hass: HomeAssistant,
    mock_config_entry_data: MappingProxyType[str, any],
    mock_tiltpi_client: MagicMock,
) -> None:
    """Test error shown when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    mock_tiltpi_client.get_hydrometers.side_effect = TimeoutError()

    with patch(
        "homeassistant.components.tilt_pi.config_flow.TiltPiClient",
        return_value=mock_tiltpi_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=mock_config_entry_data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
