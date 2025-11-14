"""Test mathematical and statistical functions for Home Assistant templates."""

from __future__ import annotations

import math

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError

from tests.helpers.template.helpers import render


def test_math_constants(hass: HomeAssistant) -> None:
    """Test math constants."""
    assert render(hass, "{{ e }}") == math.e
    assert render(hass, "{{ pi }}") == math.pi
    assert render(hass, "{{ tau }}") == math.pi * 2


def test_logarithm(hass: HomeAssistant) -> None:
    """Test logarithm."""
    tests = [
        (4, 2, 2.0),
        (1000, 10, 3.0),
        (math.e, "", 1.0),  # The "" means the default base (e) will be used
    ]

    for value, base, expected in tests:
        assert render(hass, f"{{{{ {value} | log({base}) | round(1) }}}}") == expected

        assert render(hass, f"{{{{ log({value}, {base}) | round(1) }}}}") == expected

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ invalid | log(_) }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ log(invalid, _) }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ 10 | log(invalid) }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ log(10, invalid) }}")

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | log(10, 1) }}") == 1
    assert render(hass, "{{ 'no_number' | log(10, default=1) }}") == 1
    assert render(hass, "{{ log('no_number', 10, 1) }}") == 1
    assert render(hass, "{{ log('no_number', 10, default=1) }}") == 1
    assert render(hass, "{{ log(0, 10, 1) }}") == 1
    assert render(hass, "{{ log(0, 10, default=1) }}") == 1


def test_sine(hass: HomeAssistant) -> None:
    """Test sine."""
    tests = [
        (0, 0.0),
        (math.pi / 2, 1.0),
        (math.pi, 0.0),
        (math.pi * 1.5, -1.0),
        (math.pi / 10, 0.309),
    ]

    for value, expected in tests:
        assert render(hass, f"{{{{ {value} | sin | round(3) }}}}") == expected
        assert render(hass, f"{{{{ sin({value}) | round(3) }}}}") == expected

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'duck' | sin }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ invalid | sin('duck') }}")

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | sin(1) }}") == 1
    assert render(hass, "{{ 'no_number' | sin(default=1) }}") == 1
    assert render(hass, "{{ sin('no_number', 1) }}") == 1
    assert render(hass, "{{ sin('no_number', default=1) }}") == 1


def test_cosine(hass: HomeAssistant) -> None:
    """Test cosine."""
    tests = [
        (0, 1.0),
        (math.pi / 2, 0.0),
        (math.pi, -1.0),
        (math.pi * 1.5, 0.0),
        (math.pi / 3, 0.5),
    ]

    for value, expected in tests:
        assert render(hass, f"{{{{ {value} | cos | round(3) }}}}") == expected
        assert render(hass, f"{{{{ cos({value}) | round(3) }}}}") == expected

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'duck' | cos }}")

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | cos(1) }}") == 1
    assert render(hass, "{{ 'no_number' | cos(default=1) }}") == 1
    assert render(hass, "{{ cos('no_number', 1) }}") == 1
    assert render(hass, "{{ cos('no_number', default=1) }}") == 1


def test_tangent(hass: HomeAssistant) -> None:
    """Test tangent."""
    tests = [
        (0, 0.0),
        (math.pi / 4, 1.0),
        (math.pi, 0.0),
        (math.pi / 6, 0.577),
    ]

    for value, expected in tests:
        assert render(hass, f"{{{{ {value} | tan | round(3) }}}}") == expected
        assert render(hass, f"{{{{ tan({value}) | round(3) }}}}") == expected

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'duck' | tan }}")

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | tan(1) }}") == 1
    assert render(hass, "{{ 'no_number' | tan(default=1) }}") == 1
    assert render(hass, "{{ tan('no_number', 1) }}") == 1
    assert render(hass, "{{ tan('no_number', default=1) }}") == 1


def test_square_root(hass: HomeAssistant) -> None:
    """Test square root."""
    tests = [
        (0, 0.0),
        (1, 1.0),
        (4, 2.0),
        (9, 3.0),
        (16, 4.0),
        (0.25, 0.5),
    ]

    for value, expected in tests:
        assert render(hass, f"{{{{ {value} | sqrt }}}}") == expected
        assert render(hass, f"{{{{ sqrt({value}) }}}}") == expected

    # Test handling of invalid input
    with pytest.raises(TemplateError):
        render(hass, "{{ 'duck' | sqrt }}")
    with pytest.raises(TemplateError):
        render(hass, "{{ -1 | sqrt }}")

    # Test handling of default return value
    assert render(hass, "{{ 'no_number' | sqrt(1) }}") == 1
    assert render(hass, "{{ 'no_number' | sqrt(default=1) }}") == 1
    assert render(hass, "{{ sqrt('no_number', 1) }}") == 1
    assert render(hass, "{{ sqrt('no_number', default=1) }}") == 1
    assert render(hass, "{{ sqrt(-1, 1) }}") == 1
    assert render(hass, "{{ sqrt(-1, default=1) }}") == 1


def test_arc_functions(hass: HomeAssistant) -> None:
    """Test arc trigonometric functions."""
    # Test arc sine
    assert render(hass, "{{ asin(0.5) | round(3) }}") == round(math.asin(0.5), 3)
    assert render(hass, "{{ 0.5 | asin | round(3) }}") == round(math.asin(0.5), 3)

    # Test arc cosine
    assert render(hass, "{{ acos(0.5) | round(3) }}") == round(math.acos(0.5), 3)
    assert render(hass, "{{ 0.5 | acos | round(3) }}") == round(math.acos(0.5), 3)

    # Test arc tangent
    assert render(hass, "{{ atan(1) | round(3) }}") == round(math.atan(1), 3)
    assert render(hass, "{{ 1 | atan | round(3) }}") == round(math.atan(1), 3)

    # Test atan2
    assert render(hass, "{{ atan2(1, 1) | round(3) }}") == round(math.atan2(1, 1), 3)
    assert render(hass, "{{ atan2([1, 1]) | round(3) }}") == round(math.atan2(1, 1), 3)

    # Test invalid input handling
    with pytest.raises(TemplateError):
        render(hass, "{{ asin(2) }}")  # Outside domain [-1, 1]

    # Test default values
    assert render(hass, "{{ asin(2, 1) }}") == 1
    assert render(hass, "{{ acos(2, 1) }}") == 1
    assert render(hass, "{{ atan('invalid', 1) }}") == 1
    assert render(hass, "{{ atan2('invalid', 1, 1) }}") == 1


def test_average(hass: HomeAssistant) -> None:
    """Test the average function."""
    assert render(hass, "{{ average([1, 2, 3]) }}") == 2
    assert render(hass, "{{ average(1, 2, 3) }}") == 2

    # Testing of default values
    assert render(hass, "{{ average([1, 2, 3], -1) }}") == 2
    assert render(hass, "{{ average([], -1) }}") == -1
    assert render(hass, "{{ average([], default=-1) }}") == -1
    assert render(hass, "{{ average([], 5, default=-1) }}") == -1
    assert render(hass, "{{ average(1, 'a', 3, default=-1) }}") == -1

    with pytest.raises(TemplateError):
        render(hass, "{{ average() }}")

    with pytest.raises(TemplateError):
        render(hass, "{{ average([]) }}")


def test_median(hass: HomeAssistant) -> None:
    """Test the median function."""
    assert render(hass, "{{ median([1, 2, 3]) }}") == 2
    assert render(hass, "{{ median([1, 2, 3, 4]) }}") == 2.5
    assert render(hass, "{{ median(1, 2, 3) }}") == 2

    # Testing of default values
    assert render(hass, "{{ median([1, 2, 3], -1) }}") == 2
    assert render(hass, "{{ median([], -1) }}") == -1
    assert render(hass, "{{ median([], default=-1) }}") == -1

    with pytest.raises(TemplateError):
        render(hass, "{{ median() }}")

    with pytest.raises(TemplateError):
        render(hass, "{{ median([]) }}")


def test_statistical_mode(hass: HomeAssistant) -> None:
    """Test the statistical mode function."""
    assert render(hass, "{{ statistical_mode([1, 1, 2, 3]) }}") == 1
    assert render(hass, "{{ statistical_mode(1, 1, 2, 3) }}") == 1

    # Testing of default values
    assert render(hass, "{{ statistical_mode([1, 1, 2], -1) }}") == 1
    assert render(hass, "{{ statistical_mode([], -1) }}") == -1
    assert render(hass, "{{ statistical_mode([], default=-1) }}") == -1

    with pytest.raises(TemplateError):
        render(hass, "{{ statistical_mode() }}")

    with pytest.raises(TemplateError):
        render(hass, "{{ statistical_mode([]) }}")


def test_min_max_functions(hass: HomeAssistant) -> None:
    """Test min and max functions."""
    # Test min function
    assert render(hass, "{{ min([1, 2, 3]) }}") == 1
    assert render(hass, "{{ min(1, 2, 3) }}") == 1

    # Test max function
    assert render(hass, "{{ max([1, 2, 3]) }}") == 3
    assert render(hass, "{{ max(1, 2, 3) }}") == 3

    # Test error handling
    with pytest.raises(TemplateError):
        render(hass, "{{ min() }}")

    with pytest.raises(TemplateError):
        render(hass, "{{ max() }}")


def test_bitwise_and(hass: HomeAssistant) -> None:
    """Test bitwise and."""
    assert render(hass, "{{ bitwise_and(8, 2) }}") == 0
    assert render(hass, "{{ bitwise_and(10, 2) }}") == 2
    assert render(hass, "{{ bitwise_and(8, 8) }}") == 8


def test_bitwise_or(hass: HomeAssistant) -> None:
    """Test bitwise or."""
    assert render(hass, "{{ bitwise_or(8, 2) }}") == 10
    assert render(hass, "{{ bitwise_or(8, 8) }}") == 8
    assert render(hass, "{{ bitwise_or(10, 2) }}") == 10


def test_bitwise_xor(hass: HomeAssistant) -> None:
    """Test bitwise xor."""
    assert render(hass, "{{ bitwise_xor(8, 2) }}") == 10
    assert render(hass, "{{ bitwise_xor(8, 8) }}") == 0
    assert render(hass, "{{ bitwise_xor(10, 2) }}") == 8


@pytest.mark.parametrize(
    "attribute",
    [
        "a",
        "b",
        "c",
    ],
)
def test_min_max_attribute(hass: HomeAssistant, attribute) -> None:
    """Test the min and max filters with attribute."""
    hass.states.async_set(
        "test.object",
        "test",
        {
            "objects": [
                {
                    "a": 1,
                    "b": 2,
                    "c": 3,
                },
                {
                    "a": 2,
                    "b": 1,
                    "c": 2,
                },
                {
                    "a": 3,
                    "b": 3,
                    "c": 1,
                },
            ],
        },
    )
    assert (
        render(
            hass,
            f"{{{{ (state_attr('test.object', 'objects') | min(attribute='{attribute}'))['{attribute}']}}}}",
        )
        == 1
    )
    assert (
        render(
            hass,
            f"{{{{ (min(state_attr('test.object', 'objects'), attribute='{attribute}'))['{attribute}']}}}}",
        )
        == 1
    )
    assert (
        render(
            hass,
            f"{{{{ (state_attr('test.object', 'objects') | max(attribute='{attribute}'))['{attribute}']}}}}",
        )
        == 3
    )
    assert (
        render(
            hass,
            f"{{{{ (max(state_attr('test.object', 'objects'), attribute='{attribute}'))['{attribute}']}}}}",
        )
        == 3
    )
