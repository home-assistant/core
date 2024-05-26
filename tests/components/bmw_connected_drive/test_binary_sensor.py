"""Test BMW binary sensors."""

from freezegun import freeze_time
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

# from bimmer_connected.vehicle.reports import ConditionBasedServiceReport
from . import setup_mocked_integration


@freeze_time("2023-06-22 10:30:00+00:00")
async def test_entity_state_attrs(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all select entities
    assert hass.states.async_all("binary_sensor") == snapshot
