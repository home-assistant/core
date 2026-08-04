"""Test the IntelliClima integration setup."""

from unittest.mock import AsyncMock

from pyintelliclima.api import IntelliClimaAPIError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_succeeds_when_filter_status_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test the config entry still loads when the filter-status endpoint fails.

    Filter status only backs a diagnostic binary sensor, so a transient
    failure of that ancillary endpoint must not block the fan, select, and
    sensor platforms from being set up.
    """
    mock_cloud_interface.get_filter_status.side_effect = IntelliClimaAPIError(
        "cannot compute filter status"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("fan.test_vmc") is not None

    state = hass.states.get("binary_sensor.filter_cleaning_required")
    assert state is not None
    assert state.state == "unavailable"
