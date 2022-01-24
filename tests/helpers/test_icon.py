"""Test Home Assistant icon util methods."""


def test_battery_icon():
    """Test icon generator for battery sensor."""
    from homeassistant.helpers.icon import icon_for_battery_level

    assert icon_for_battery_level(None, True) == "mdi:battery-unknown"
    assert icon_for_battery_level(None, False) == "mdi:battery-unknown"

    assert icon_for_battery_level(5, True) == "mdi:battery-outline"
    assert icon_for_battery_level(5, False) == "mdi:battery-alert"

    assert icon_for_battery_level(100, True) == "mdi:battery-charging-100"
    assert icon_for_battery_level(100, False) == "mdi:battery"

    iconbase = "mdi:battery"
    for level in range(0, 100, 5):
        print(
            "Level: %d. icon: %s, charging: %s"
            % (
                level,
                icon_for_battery_level(level, False),
                icon_for_battery_level(level, True),
            )
        )
        if level <= 10:
            postfix_charging = "-outline"
        elif level <= 30:
            postfix_charging = "-charging-20"
        elif level <= 50:
            postfix_charging = "-charging-40"
        elif level <= 70:
            postfix_charging = "-charging-60"
        elif level <= 90:
            postfix_charging = "-charging-80"
        else:
            postfix_charging = "-charging-100"
        if 5 < level < 95:
            postfix = f"-{int(round(level / 10 - 0.01)) * 10}"
        elif level <= 5:
            postfix = "-alert"
        else:
            postfix = ""
        assert iconbase + postfix == icon_for_battery_level(level, False)
        assert iconbase + postfix_charging == icon_for_battery_level(level, True)


def test_signal_icon():
    """Test icon generator for signal sensor."""
    from homeassistant.helpers.icon import icon_for_signal_level

    assert icon_for_signal_level(None) == "mdi:signal-cellular-outline"
    assert icon_for_signal_level(0) == "mdi:signal-cellular-outline"
    assert icon_for_signal_level(5) == "mdi:signal-cellular-1"
    assert icon_for_signal_level(40) == "mdi:signal-cellular-2"
    assert icon_for_signal_level(80) == "mdi:signal-cellular-3"
    assert icon_for_signal_level(100) == "mdi:signal-cellular-3"


def test_volume_icon():
    """Test icon generator for signal sensor."""
    from homeassistant.helpers.icon import icon_for_volume_level

    assert icon_for_volume_level(None, True) == "mdi:volume-variant-off"
    assert icon_for_volume_level(None, False) == "mdi:volume-variant-off"

    assert icon_for_volume_level(0, True) == "mdi:volume-mute"
    assert icon_for_volume_level(0, False) == "mdi:volume-off"

    assert icon_for_volume_level(35, True) == "mdi:volume-mute"
    assert icon_for_volume_level(35, False) == "mdi:volume-low"

    assert icon_for_volume_level(70, True) == "mdi:volume-mute"
    assert icon_for_volume_level(70, False) == "mdi:volume-medium"

    assert icon_for_volume_level(70, True) == "mdi:volume-mute"
    assert icon_for_volume_level(70, False) == "mdi:volume-high"
