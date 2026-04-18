"""Test the Tilt config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_async_step_user_gets_form_and_creates_entry(
    hass: HomeAssistant,
    mock_tiltpi_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that the we can view the form and that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://192.168.1.123:1880"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
        CONF_PORT: 1880,
    }


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that we abort if we attempt to submit the same entry twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://192.168.1.123:1880"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_successful_recovery_after_invalid_host(
    hass: HomeAssistant,
    mock_tiltpi_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error shown when user submits invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Simulate a invalid host error by providing an invalid URL
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "not-a-valid-url"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"url": "invalid_host"}

    # Demonstrate successful connection on retry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://192.168.1.123:1880"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
        CONF_PORT: 1880,
    }


async def test_successful_recovery_after_connection_error(
    hass: HomeAssistant,
    mock_tiltpi_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error shown when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Simulate a connection error by raising a TimeoutError
    mock_tiltpi_client.get_hydrometers.side_effect = TimeoutError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://192.168.1.123:1880"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Simulate successful connection on retry
    mock_tiltpi_client.get_hydrometers.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://192.168.1.123:1880"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
        CONF_PORT: 1880,
    }
