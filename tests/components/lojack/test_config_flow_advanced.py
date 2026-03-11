"""Advanced tests for the LoJack config flow and initialization."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.lojack.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import MockApiError
from .const import TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry


def _make_client(**kwargs) -> AsyncMock:
    """Build a minimal mock client for config flow tests."""
    client = AsyncMock()
    client.user_id = kwargs.get("user_id", "user123")
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


async def test_config_flow_validate_input_succeeds(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow validation succeeds with a valid client."""
    client = _make_client(user_id="unique_user_id")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lojack.config_flow.LoJackClient.create",
        return_value=client,
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
    assert result["result"].unique_id == "unique_user_id"




async def test_setup_entry_client_close_error_on_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup handles close errors gracefully when list_devices fails."""
    client = AsyncMock()
    client.list_devices = AsyncMock(side_effect=MockApiError("API error"))
    client.close = AsyncMock(side_effect=Exception("Close failed"))

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # ApiError on list_devices → ConfigEntryNotReady
    assert mock_config_entry.state.name == "SETUP_RETRY"


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
