"""Helper for HomematicIP Cloud Tests."""


def get_and_check_device_basics(hass, device_id, device_name, device_model):
    """Get and test basic device."""

    device = hass.states.get(device_id)
    assert device is not None
    assert device.attributes["model_type"] == device_model
    assert device.name == device_name
    return device
