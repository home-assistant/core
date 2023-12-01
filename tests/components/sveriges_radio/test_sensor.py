"""Tests for sensor module in Sveriges Radio integrations."""
import pytest

from homeassistant.components.sveriges_radio.const import CONF_AREA, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_AREA: "Norrbotten",
}


@pytest.fixture(name="load_integration")
async def load_integration_from_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Describe function."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="123",
    )

    config_entry.add_to_hass(hass)

    return config_entry


async def test_sensor(
    hass: HomeAssistant,
    load_integration: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Sveriges Radio sensor."""
    assert "sensor.Area" in entity_registry.entities


# @pytest.fixture(name="load_int")
# async def load_integration_from_entry(
#    hass: HomeAssistant, get_ferries: list[FerryStop]
# ) -> MockConfigEntry:
#    """Set up the Trafikverket Ferry integration in Home Assistant."""
#    config_entry = MockConfigEntry(
#        domain=DOMAIN,
#        source=SOURCE_USER,
#        data=ENTRY_CONFIG,
#        entry_id="1",
#        unique_id="123",
#    )
#
#    config_entry.add_to_hass(hass)
#
#    with patch(
#        "homeassistant.components.trafikverket_ferry.coordinator.TrafikverketFerry.async_get_next_ferry_stops",
#        return_value=get_ferries,
#    ):
#        await hass.config_entries.async_setup(config_entry.entry_id)
#        await hass.async_block_till_done()
#
#    return config_entry

# ENTRY_CONFIG = {
#    CONF_API_KEY: "1234567890",
#    CONF_FROM: "Harbor 1",
#    CONF_TO: "Harbor 2",
#    CONF_TIME: "00:00:00",
#    CONF_WEEKDAY: WEEKDAYS,
#    CONF_NAME: "Harbor1",
# }


# def test_get_traffic_info_expected_behaviour() -> None:
#    # set up
#    traffic_sensor = TrafficSensor()
#    requests = create_autospec(requests)
#    with open("sr_traffic_api_mock_return_value.txt", encoding='utf-8') as f:
#        api_response = f.readlines()
#    requests.get.return_value = api_response
#
#    # test
#    output = traffic_sensor._get_traffic_info()
#
#    assert output ==
