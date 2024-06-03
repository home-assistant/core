"""Test BMW binary sensors."""

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_mocked_integration


@freeze_time("2023-06-22 10:30:00+00:00")
@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state_attrs(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all binary_sensor entities
    assert hass.states.async_all("binary_sensor") == snapshot
