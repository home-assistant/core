"""Define tests for the The Things Network coordinator."""

import pytest
from ttn_client import TTNAuthError

from homeassistant.core import HomeAssistant

from .conftest import CONFIG_ENTRY


@pytest.mark.parametrize(("exception_class"), [TTNAuthError, Exception])
async def test_client_exceptions(
    hass: HomeAssistant, mock_TTNClient, exception_class
) -> None:
    """Test TTN Exceptions."""

    mock_TTNClient.return_value.fetch_data.side_effect = exception_class
    CONFIG_ENTRY.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(CONFIG_ENTRY.entry_id)
