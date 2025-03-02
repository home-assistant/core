"""Define tests for the The Things Network init."""

import pytest
from ttn_client import TTNAuthError

from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(("exception_class"), [TTNAuthError, Exception])
async def test_init_exceptions(
    hass: HomeAssistant, mock_ttnclient, exception_class, mock_config_entry
) -> None:
    """Test TTN Exceptions."""

    mock_ttnclient.return_value.fetch_data.side_effect = exception_class
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
