"""Test the lg_soundbar media player."""

from unittest.mock import patch

import temescal

from homeassistant.components.lg_soundbar.media_player import LGDevice

AVAILABLE_FUNCTIONS = [
    temescal.functions.index("Wi-Fi"),
    temescal.functions.index("Bluetooth"),
    temescal.functions.index("Optical/HDMI ARC"),
    temescal.functions.index("HDMI"),
    temescal.functions.index("USB2"),
]


def create_device(current_function: str) -> LGDevice:
    """Create a device reporting the given function as the current one."""
    device = LGDevice("127.0.0.1", 9741, "unique_id")
    with patch.object(LGDevice, "schedule_update_ha_state"):
        device.handle_event(
            {
                "msg": "FUNC_VIEW_INFO",
                "data": {
                    "i_curr_func": temescal.functions.index(current_function),
                    "ai_func_list": AVAILABLE_FUNCTIONS,
                },
            }
        )
    return device


def test_source_reported_as_is_when_available() -> None:
    """Test that a function offered by the device is reported unchanged."""
    assert create_device("Bluetooth").source == "Bluetooth"


def test_source_falls_back_to_available_equivalent() -> None:
    """Test that a function missing from the list falls back to an equivalent one.

    Soundbars report states such as E-ARC or HDMI3 that they never offer in
    ai_func_list, which leaves the current source outside of source_list.
    """
    assert create_device("E-ARC").source == "Optical/HDMI ARC"
    assert create_device("ARC").source == "Optical/HDMI ARC"
    assert create_device("HDMI3").source == "HDMI"
    assert create_device("USB").source == "USB2"


def test_source_kept_when_no_equivalent_is_available() -> None:
    """Test that a function without an available equivalent is reported as is."""
    assert create_device("Aux").source == "Aux"


def test_source_list_only_contains_offered_functions() -> None:
    """Test that the source list is not extended by the fallback."""
    assert create_device("E-ARC").source_list == [
        "Bluetooth",
        "HDMI",
        "Optical/HDMI ARC",
        "USB2",
        "Wi-Fi",
    ]


def test_source_unknown_before_any_response() -> None:
    """Test that no source is reported before the device answers."""
    assert LGDevice("127.0.0.1", 9741, "unique_id").source is None
