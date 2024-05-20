"""Testing for the icons."""

import pytest

from homeassistant.components.weatherflow_cloud.sensor import wind_angle_icon_fn


@pytest.mark.parametrize(
    "wind_direction, expected_icon",  # noqa: PT006
    [
        (0, "mdi:arrow-up-thin"),
        (1, "mdi:arrow-up-thin"),  # Just after North transition
        (5, "mdi:arrow-up-thin"),
        (22, "mdi:arrow-up-thin"),  # Just before North-East transition
        (23, "mdi:arrow-top-right-thin"),
        (24, "mdi:arrow-top-right-thin"),  # Just after North-East transition
        (67, "mdi:arrow-top-right-thin"),  # Just before East transition
        (68, "mdi:arrow-right-thin"),
        (69, "mdi:arrow-right-thin"),  # Just after East transition
        (45, "mdi:arrow-top-right-thin"),
        (90, "mdi:arrow-right-thin"),
        (112, "mdi:arrow-right-thin"),  # Just before South-East transition
        (113, "mdi:arrow-bottom-right-thin"),
        (114, "mdi:arrow-bottom-right-thin"),  # Just after South-East transition
        (157, "mdi:arrow-bottom-right-thin"),  # Just before South transition
        (158, "mdi:arrow-down-thin"),
        (159, "mdi:arrow-down-thin"),  # Just after South transition
        (202, "mdi:arrow-down-thin"),  # Just before South-West transition
        (203, "mdi:arrow-bottom-left-thin"),
        (204, "mdi:arrow-bottom-left-thin"),  # Just after South-West transition
        (247, "mdi:arrow-bottom-left-thin"),  # Just before West transition
        (248, "mdi:arrow-left-thin"),
        (249, "mdi:arrow-left-thin"),  # Just after West transition
        (292, "mdi:arrow-left-thin"),  # Just before North-West transition
        (293, "mdi:arrow-top-left-thin"),
        (294, "mdi:arrow-top-left-thin"),  # Just after North-West transition
        (337, "mdi:arrow-top-left-thin"),  # Just before North transition
        (338, "mdi:arrow-up-thin"),
        (339, "mdi:arrow-up-thin"),  # Just after North transition
        (360, "mdi:arrow-up-thin"),  # Edge case: wind direction is exactly 360 degrees
        (135, "mdi:arrow-bottom-right-thin"),
        (180, "mdi:arrow-down-thin"),
        (225, "mdi:arrow-bottom-left-thin"),
        (270, "mdi:arrow-left-thin"),
        (359, "mdi:arrow-up-thin"),
    ],
)
def test_wind_direction_icon_fn_and_cardinal(wind_direction, expected_icon):
    """Test the cardinal directions are correct."""
    direction_icon = wind_angle_icon_fn(wind_direction)
    assert direction_icon == expected_icon
