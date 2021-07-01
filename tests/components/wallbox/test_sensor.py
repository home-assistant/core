"""Test Wallbox Switch component."""

from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry
from tests.components.wallbox import setup_integration

entry = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_STATION: "12345",
    },
    entry_id="testEntry",
)


async def test_wallbox_sensor_class(hass):
    """Test wallbox sensor class."""

    await setup_integration(hass)

    state = hass.states.get("sensor.mock_title_charging_power")
    assert state.attributes["unit_of_measurement"] == "kW"
    assert state.attributes["icon"] == "mdi:ev-station"
    assert state.name == "Mock Title Charging Power"

    state = hass.states.get("sensor.mock_title_charging_speed")
    assert state.attributes["icon"] == "mdi:speedometer"
    assert state.name == "Mock Title Charging Speed"
