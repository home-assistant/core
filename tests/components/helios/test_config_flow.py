"""Test the Helios config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from helios_websocket_api import HeliosApiException
import pytest

from homeassistant import config_entries
from homeassistant.components.helios.config_flow import InvalidHost, validate_host
from homeassistant.components.helios.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_helios_client: MagicMock
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Helios"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_NAME: "Helios",
    }
    mock_helios_client.fetch_metric_data.assert_called_once()


async def test_user_flow_invalid_host(
    hass: HomeAssistant, mock_helios_client: MagicMock
) -> None:
    """Test user flow with invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "invalid-hostname"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    mock_helios_client.fetch_metric_data.assert_not_called()


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_helios_client: MagicMock
) -> None:
    """Test user flow when cannot connect to device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_helios_client.fetch_metric_data.side_effect = HeliosApiException(
        "Connection failed"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "cannot_connect"}
    mock_helios_client.fetch_metric_data.assert_called_once()


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_helios_client: MagicMock
) -> None:
    """Test user flow with unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_helios_client.fetch_metric_data.side_effect = Exception("Unknown error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "unknown"}
    mock_helios_client.fetch_metric_data.assert_called_once()


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_helios_client: MagicMock
) -> None:
    """Test user flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_helios_client.fetch_metric_data.assert_not_called()


async def test_reconfigure_flow_show_form(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow shows form with current host."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helios_client: MagicMock,
) -> None:
    """Test successful reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    mock_helios_client.fetch_metric_data.assert_called_once()


async def test_reconfigure_flow_same_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helios_client: MagicMock,
) -> None:
    """Test reconfigure flow with same host."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"
    mock_helios_client.fetch_metric_data.assert_called_once()


async def test_reconfigure_flow_invalid_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helios_client: MagicMock,
) -> None:
    """Test reconfigure flow with invalid host."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "invalid-hostname"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    mock_helios_client.fetch_metric_data.assert_not_called()


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helios_client: MagicMock,
) -> None:
    """Test reconfigure flow when cannot connect."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    mock_helios_client.fetch_metric_data.side_effect = HeliosApiException(
        "Connection failed"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_HOST: "cannot_connect"}
    mock_helios_client.fetch_metric_data.assert_called_once()


async def test_reconfigure_flow_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helios_client: MagicMock,
) -> None:
    """Test reconfigure flow with unknown error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    mock_helios_client.fetch_metric_data.side_effect = Exception("Unknown error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_HOST: "unknown"}
    mock_helios_client.fetch_metric_data.assert_called_once()


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helios_client: MagicMock,
) -> None:
    """Test reconfigure flow when new host is already configured."""
    mock_config_entry.add_to_hass(hass)

    # Add another config entry with different host
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Helios",
        data={
            CONF_HOST: "192.168.1.200",
            CONF_NAME: "Helios",
        },
    )
    other_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_helios_client.fetch_metric_data.assert_not_called()


async def test_validate_host_success(hass: HomeAssistant) -> None:
    """Test validate_host with valid IP address."""
    with patch(
        "homeassistant.components.helios.config_flow.Helios"
    ) as mock_helios_class:
        mock_client = mock_helios_class.return_value
        mock_client.fetch_metric_data = AsyncMock()

        # Should not raise any exception
        await validate_host(hass, "192.168.1.100")

        mock_helios_class.assert_called_once_with("192.168.1.100")
        mock_client.fetch_metric_data.assert_called_once()


async def test_validate_host_invalid_ip(hass: HomeAssistant) -> None:
    """Test validate_host with invalid IP address."""
    with pytest.raises(InvalidHost, match="Invalid IP address: invalid-host"):
        await validate_host(hass, "invalid-host")


async def test_validate_host_connection_error(hass: HomeAssistant) -> None:
    """Test validate_host when connection fails."""
    with patch(
        "homeassistant.components.helios.config_flow.Helios"
    ) as mock_helios_class:
        mock_client = mock_helios_class.return_value
        mock_client.fetch_metric_data = AsyncMock(
            side_effect=HeliosApiException("Connection failed")
        )

        with pytest.raises(HeliosApiException, match="Connection failed"):
            await validate_host(hass, "192.168.1.100")


def test_invalid_host_exception() -> None:
    """Test InvalidHost exception is a HomeAssistantError."""
    exception = InvalidHost("Test error")
    assert isinstance(exception, HomeAssistantError)
    assert str(exception) == "Test error"
