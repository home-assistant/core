"""Test Hydrawise switch."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_states(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
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
    assert auto_watering2.state == "off"


async def test_manual_watering_services(
    hass: HomeAssistant, mock_added_config_entry: MockConfigEntry, mock_pydrawise: Mock
) -> None:
    """Test Manual Watering services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_manual_watering"},
        blocking=True,
    )
    mock_pydrawise.run_zone.assert_called_once_with(15, 1)
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_manual_watering"},
        blocking=True,
    )
    mock_pydrawise.run_zone.assert_called_once_with(0, 1)


async def test_auto_watering_services(
    hass: HomeAssistant, mock_added_config_entry: MockConfigEntry, mock_pydrawise: Mock
) -> None:
    """Test Automatic Watering services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_automatic_watering"},
        blocking=True,
    )
    mock_pydrawise.suspend_zone.assert_called_once_with(365, 1)
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_automatic_watering"},
        blocking=True,
    )
    mock_pydrawise.suspend_zone.assert_called_once_with(0, 1)
