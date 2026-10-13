"""The binary sensor tests for the powerwall platform."""

from unittest.mock import patch

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .mocks import _mock_powerwall_restricted, _mock_powerwall_with_fixtures

from tests.common import MockConfigEntry


async def test_sensors(hass: HomeAssistant) -> None:
    """Test creation of the binary sensors."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.mysite_grid_services_active")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "MySite Grid services active",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("binary_sensor.mysite_grid_status")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "MySite Grid status",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("binary_sensor.mysite_status")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "MySite Status",
        "device_class": "power",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("binary_sensor.mysite_connected_to_tesla")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "MySite Connected to Tesla",
        "device_class": "connectivity",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())

    state = hass.states.get("binary_sensor.mysite_charging")
    assert state.state == STATE_ON
    expected_attributes = {
        "friendly_name": "MySite Charging",
        "device_class": "battery_charging",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


async def test_sensors_with_empty_meters(hass: HomeAssistant) -> None:
    """Test creation of the binary sensors with empty meters."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass, empty_meters=True)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.mysite_charging")
    assert state.state == STATE_UNAVAILABLE


async def test_pw3_restricted_entities(hass: HomeAssistant) -> None:
    """Restricted PW3 surface should only expose the three meter-driven binary sensors."""
    mock_powerwall = await _mock_powerwall_restricted(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4"},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.powerwall_1_2_3_4_grid_services_active")
        is not None
    )
    assert hass.states.get("binary_sensor.powerwall_1_2_3_4_grid_status") is not None
    assert hass.states.get("binary_sensor.powerwall_1_2_3_4_charging") is not None
    # Running and Connected sensors require sitemaster which 404s on PW3.
    assert hass.states.get("binary_sensor.powerwall_1_2_3_4_status") is None
    assert hass.states.get("binary_sensor.powerwall_1_2_3_4_connected_to_tesla") is None
