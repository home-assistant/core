"""The sensor tests for the nut platform."""


from .util import async_init_integration


async def test_pr3000rt2u(hass):
    """Test creation of PR3000RT2U sensors."""

    await async_init_integration(hass, "PR3000RT2U", ["battery.charge"])

    state = hass.states.get("sensor.ups1_battery_charge")
    assert state.state == "100"

    expected_attributes = {
        "device_class": "battery",
        "friendly_name": "Ups1 Battery Charge",
        "state": "Online",
        "unit_of_measurement": "%",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == expected_attributes[key] for key in expected_attributes
    )


async def test_cp1350c(hass):
    """Test creation of CP1350C sensors."""

    await async_init_integration(hass, "CP1350C", ["battery.charge"])

    state = hass.states.get("sensor.ups1_battery_charge")
    assert state.state == "100"

    expected_attributes = {
        "device_class": "battery",
        "friendly_name": "Ups1 Battery Charge",
        "state": "Online",
        "unit_of_measurement": "%",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == expected_attributes[key] for key in expected_attributes
    )


async def test_5e850i(hass):
    """Test creation of 5E850I sensors."""

    await async_init_integration(hass, "5E850I", ["battery.charge"])

    state = hass.states.get("sensor.ups1_battery_charge")
    assert state.state == "100"

    expected_attributes = {
        "device_class": "battery",
        "friendly_name": "Ups1 Battery Charge",
        "state": "Online",
        "unit_of_measurement": "%",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == expected_attributes[key] for key in expected_attributes
    )
