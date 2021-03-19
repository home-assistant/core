"""The test for the Salus data update coordinator."""
from unittest.mock import MagicMock, Mock

import pytest
from requests import HTTPError

from homeassistant.components.salus.coordinator import SalusDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .mocks import MOCK_DEVICE_ID, _get_mock_salus


async def test_coordinator_update_error(hass):
    """Test getting an error on data update."""
    mock_salus = _get_mock_salus()
    mock_get_device_readings = MagicMock()
    mock_get_device_readings.side_effect = HTTPError(Mock(status=500), "unknown")
    type(mock_salus).get_device_reading = mock_get_device_readings

    coordinator = SalusDataUpdateCoordinator(
        hass,
        api=mock_salus,
        device_id=MOCK_DEVICE_ID,
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    mock_get_device_readings.assert_called_once_with(MOCK_DEVICE_ID)
