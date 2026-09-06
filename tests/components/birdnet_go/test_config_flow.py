"""Test the BirdNET-Go config flow."""

from unittest.mock import AsyncMock, patch

from aiobirdnetgo import (
    BirdNetGoAuthenticationError,
    BirdNetGoConnectionError,
    BirdNetGoError,
    BirdNetGoResponseError,
)

from homeassistant.components.birdnet_go.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_flow_user_success(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test successful user step configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BirdNET-Go (192.168.1.100:8080)"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_SSL: False,
    }
    assert isinstance(result["data"][CONF_PORT], int)
    assert result["result"].unique_id == "192.168.1.100:8080"


async def test_flow_user_ipv6(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with IPv6 address."""
    mock_birdnet_client.host = "2001:db8::1"
    mock_birdnet_client.port = 8080

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "[2001:db8::1]",
            CONF_PORT: 8080,
            CONF_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BirdNET-Go (2001:db8::1:8080)"
    assert result["data"] == {
        CONF_HOST: "2001:db8::1",
        CONF_PORT: 8080,
        CONF_SSL: False,
    }
    assert result["result"].unique_id == "2001:db8::1:8080"


async def test_flow_user_port_normalization(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step normalizes float port from NumberSelector and host whitespace."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "  192.168.1.100  ",
            CONF_PORT: 8080.0,
            CONF_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_PORT] == 8080
    assert isinstance(result["data"][CONF_PORT], int)


async def test_flow_user_cannot_connect(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with connection error."""
    mock_birdnet_client.get_kpis.side_effect = BirdNetGoConnectionError(
        "Host unreachable"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_birdnet_client.get_kpis.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_auth_not_supported(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with authentication error returns auth_not_supported."""
    mock_birdnet_client.get_kpis.side_effect = BirdNetGoAuthenticationError(
        "Authentication required"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_not_supported"}


async def test_flow_user_invalid_url_value_error(
    hass: HomeAssistant,
) -> None:
    """Test user step when client construction raises ValueError."""
    with patch(
        "homeassistant.components.birdnet_go.config_flow.BirdNetGoClient",
        side_effect=ValueError("Invalid URL or port"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "http://bird.local:notaport",
                CONF_PORT: DEFAULT_PORT,
                CONF_SSL: False,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_malformed_kpis(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step rejects malformed KPI response from non-BirdNET endpoint."""
    mock_birdnet_client.get_kpis.side_effect = BirdNetGoResponseError(
        200, "Malformed KPI response: missing required headline metrics"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_general_error(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with general BirdNET-Go error."""
    mock_birdnet_client.get_kpis.side_effect = BirdNetGoError("General failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_unknown_exception(
    hass: HomeAssistant, mock_birdnet_client: AsyncMock
) -> None:
    """Test user step with unexpected exception."""
    mock_birdnet_client.get_kpis.side_effect = RuntimeError("Fatal memory error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_flow_user_already_configured(
    hass: HomeAssistant,
    mock_birdnet_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when unique ID is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_url_canonicalization_already_configured(
    hass: HomeAssistant,
    mock_birdnet_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when a full URL resolves to an already configured unique ID."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "http://192.168.1.100:8080/api/",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
