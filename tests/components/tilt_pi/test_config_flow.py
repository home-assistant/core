"""Test the Tilt config flow."""

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_URL
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
    assert result["errors"] == {}


async def test_async_step_user_creates_entry(
    hass: HomeAssistant,
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
            user_input={CONF_URL: "http://192.168.1.123:1880"},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_HOST: "192.168.1.123",
            CONF_PORT: 1880,
        }


async def test_async_step_user_error_invalid_host(
    hass: HomeAssistant,
    mock_tiltpi_client: MagicMock,
) -> None:
    """Test error shown when user submits invalid host."""
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
            user_input={CONF_URL: "not-a-valid-url"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"url": "invalid_host"}


async def test_async_step_user_connection_error(
    hass: HomeAssistant,
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
            user_input={CONF_URL: "http://192.168.1.123:1880"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
