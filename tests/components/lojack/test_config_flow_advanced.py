"""Advanced tests for the LoJack config flow and initialization."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.lojack.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import MockApiError, MockAuthenticationError
from .const import TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_config_flow_validate_input_no_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow validation when no devices are available."""
    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[])  # No devices
    client.close = AsyncMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.AuthenticationError",
            MockAuthenticationError,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.ApiError",
            MockApiError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"LoJack ({TEST_USERNAME})"


async def test_config_flow_validate_input_none_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow validation when list_devices returns None."""
    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=None)  # None instead of list
    client.close = AsyncMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.AuthenticationError",
            MockAuthenticationError,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.ApiError",
            MockApiError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication with unknown error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.lojack.config_flow.LoJackClient.create",
        side_effect=Exception("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "unknown"}


async def test_reconfigure_flow_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure with unknown error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.lojack.config_flow.LoJackClient.create",
        side_effect=Exception("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_flow_multiple_failures_then_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication works after multiple failures."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    # First attempt fails with invalid auth
    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockAuthenticationError("Invalid"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong1"},
        )
    assert result["errors"] == {"base": "invalid_auth"}

    # Second attempt fails with connection error
    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockApiError("Connection error"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.ApiError",
            MockApiError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong2"},
        )
    assert result["errors"] == {"base": "cannot_connect"}

    # Third attempt succeeds
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: TEST_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_setup_entry_client_close_error_on_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup handles close errors gracefully."""
    client = AsyncMock()
    client.list_devices = AsyncMock(side_effect=MockAuthenticationError("Invalid"))
    client.close = AsyncMock(side_effect=Exception("Close failed"))

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.AuthenticationError",
            MockAuthenticationError,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Auth error is caught by coordinator and raises ConfigEntryAuthFailed
        # Close error is swallowed by the finally block
        assert mock_config_entry.state.name == "SETUP_ERROR"


async def test_unload_entry_client_close_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test unload handles close errors gracefully."""
    await setup_integration(hass, mock_config_entry)

    # Make the client close fail
    mock_lojack_client.close = AsyncMock(side_effect=Exception("Close failed"))

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

    # Should still succeed in unloading even if close fails
    assert result is True


async def test_reauth_step_entry_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow starts correctly."""
    mock_config_entry.add_to_hass(hass)

    # Initiate reauth directly
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reauth",
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
            "title_placeholders": {"username": TEST_USERNAME},
        },
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
