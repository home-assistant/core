"""Test Hydrawise switch."""

from datetime import timedelta
from unittest.mock import AsyncMock

from pydrawise.schema import Zone
import pytest

from homeassistant.components.hydrawise.const import DEFAULT_WATERING_TIME
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_states(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
) -> None:
    """Test switch states."""
    watering1 = hass.states.get("switch.zone_one_manual_watering")
    assert watering1 is not None
    assert watering1.state == "off"

    watering2 = hass.states.get("switch.zone_two_manual_watering")
    assert watering2 is not None
    assert watering2.state == "on"

    auto_watering1 = hass.states.get("switch.zone_one_automatic_watering")
    assert auto_watering1 is not None
    assert auto_watering1.state == "on"

    auto_watering2 = hass.states.get("switch.zone_two_automatic_watering")
    assert auto_watering2 is not None
    assert auto_watering2.state == "on"


async def test_manual_watering_services(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test Manual Watering services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_manual_watering"},
        blocking=True,
    )
    mock_pydrawise.start_zone.assert_called_once_with(
        zones[0], custom_run_duration=DEFAULT_WATERING_TIME.total_seconds()
    )
    state = hass.states.get("switch.zone_one_manual_watering")
    assert state is not None
    assert state.state == "on"
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_manual_watering"},
        blocking=True,
    )
    mock_pydrawise.stop_zone.assert_called_once_with(zones[0])
    state = hass.states.get("switch.zone_one_manual_watering")
    assert state is not None
    assert state.state == "off"


@pytest.mark.freeze_time("2023-10-01 00:00:00+00:00")
async def test_auto_watering_services(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test Automatic Watering services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_automatic_watering"},
        blocking=True,
    )
    mock_pydrawise.suspend_zone.assert_called_once_with(
        zones[0], dt_util.now() + timedelta(days=365)
    )
    state = hass.states.get("switch.zone_one_automatic_watering")
    assert state is not None
    assert state.state == "off"
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_automatic_watering"},
        blocking=True,
    )
    mock_pydrawise.resume_zone.assert_called_once_with(zones[0])
    state = hass.states.get("switch.zone_one_automatic_watering")
    assert state is not None
    assert state.state == "on"
