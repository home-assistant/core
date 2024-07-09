"""Test the error cases in the coordinator."""

import pytest
from simplefin4py.exceptions import SimpleFinAuthError, SimpleFinPaymentRequiredError

from homeassistant.components.simplefin import SimpleFinDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from tests.common import MockConfigEntry
from tests.components.smhi.common import AsyncMock


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (SimpleFinAuthError, ConfigEntryError),
        (SimpleFinPaymentRequiredError, ConfigEntryNotReady),
    ],
)
async def test_data_update_with_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_simplefin_client: AsyncMock,
    side_effect: Exception,
    error: Exception,
) -> None:
    """Test the error cases in the coordinator."""
    mock_simplefin_client.fetch_data.side_effect = side_effect

    coordinator = SimpleFinDataUpdateCoordinator(hass, mock_simplefin_client)

    with pytest.raises(error):
        await coordinator._async_update_data()
