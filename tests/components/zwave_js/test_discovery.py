"""Test discovery of entities for device-specific schemas for the Z-Wave JS integration."""


async def test_iblinds_v2(hass, client, iblinds_v2, integration):
    """Test that an iBlinds v2.0 multilevel switch value is discovered as a cover."""
    node = iblinds_v2
    assert node.device_class.specific == "Unused"

    state = hass.states.get("light.window_blind_controller")
    assert not state

    state = hass.states.get("cover.window_blind_controller")
    assert state


async def test_ge_12730(hass, client, ge_12730, integration):
    """Test GE 12730 Fan Controller v2.0 multilevel switch is discovered as a fan."""
    node = ge_12730
    assert node.device_class.specific == "Multilevel Power Switch"

    state = hass.states.get("light.in_wall_smart_fan_control")
    assert not state

    state = hass.states.get("fan.in_wall_smart_fan_control")
    assert state
