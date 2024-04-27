"""Test Hydrawise valve."""

from unittest.mock import AsyncMock

from pydrawise.schema import Zone

from homeassistant.components.valve import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_CLOSE_VALVE, SERVICE_OPEN_VALVE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_states(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
) -> None:
    """Test valve states."""
    zone1 = hass.states.get("valve.zone_one")
    assert zone1 is not None
    assert zone1.state == "closed"

    zone2 = hass.states.get("valve.zone_two")
    assert zone2 is not None
    assert zone2.state == "open"


async def test_services(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test valve services."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_OPEN_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    mock_pydrawise.start_zone.assert_called_once_with(zones[0])
    state = hass.states.get("valve.zone_one")
    assert state is not None
    assert state.state == "open"
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLOSE_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    mock_pydrawise.stop_zone.assert_called_once_with(zones[0])
    state = hass.states.get("valve.zone_one")
    assert state is not None
    assert state.state == "closed"
