"""Provide common Renault fixtures."""
import pytest

from .const import MOCK_VEHICLES


@pytest.fixture(name="vehicle_type", params=MOCK_VEHICLES.keys())
def get_vehicle_type(request):
    """Parametrize vehicle type."""
    return request.param
