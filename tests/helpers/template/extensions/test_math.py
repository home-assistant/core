"""Test mathematical and statistical functions for Home Assistant templates."""

from __future__ import annotations

import math

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template.extensions import MathExtension

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


def test_clamp(hass: HomeAssistant) -> None:
    """Test clamp function."""
    # Test function and filter usage in templates.
    assert render(hass, "{{ clamp(15, 0, 10) }}") == 10.0
    assert render(hass, "{{ -5 | clamp(0, 10) }}") == 0.0

    # Test basic clamping behavior
    assert MathExtension.clamp(5, 0, 10) == 5.0
    assert MathExtension.clamp(-5, 0, 10) == 0.0
    assert MathExtension.clamp(15, 0, 10) == 10.0
    assert MathExtension.clamp(0, 0, 10) == 0.0
    assert MathExtension.clamp(10, 0, 10) == 10.0

    # Test with float values
    assert MathExtension.clamp(5.5, 0, 10) == 5.5
    assert MathExtension.clamp(5.5, 0.5, 10.5) == 5.5
    assert MathExtension.clamp(0.25, 0.5, 10.5) == 0.5
    assert MathExtension.clamp(11.0, 0.5, 10.5) == 10.5

    # Test with negative ranges
    assert MathExtension.clamp(-5, -10, -1) == -5.0
    assert MathExtension.clamp(-15, -10, -1) == -10.0
    assert MathExtension.clamp(0, -10, -1) == -1.0

    # Test with non-range
    assert MathExtension.clamp(5, 10, 10) == 10.0

    # Test error handling - invalid input types
    for case in (
        "{{ clamp('invalid', 0, 10) }}",
        "{{ clamp(5, 'invalid', 10) }}",
        "{{ clamp(5, 0, 'invalid') }}",
    ):
        with pytest.raises(TemplateError):
            render(hass, case)


def test_wrap(hass: HomeAssistant) -> None:
    """Test wrap function."""
    # Test function and filter usage in templates.
    assert render(hass, "{{ wrap(15, 0, 10) }}") == 5.0
    assert render(hass, "{{ -5 | wrap(0, 10) }}") == 5.0

    # Test basic wrapping behavior
    assert MathExtension.wrap(5, 0, 10) == 5.0
    assert MathExtension.wrap(10, 0, 10) == 0.0  # max wraps to min
    assert MathExtension.wrap(15, 0, 10) == 5.0
    assert MathExtension.wrap(25, 0, 10) == 5.0
    assert MathExtension.wrap(-5, 0, 10) == 5.0
    assert MathExtension.wrap(-10, 0, 10) == 0.0

    # Test angle wrapping (common use case)
    assert MathExtension.wrap(370, 0, 360) == 10.0
    assert MathExtension.wrap(-10, 0, 360) == 350.0
    assert MathExtension.wrap(720, 0, 360) == 0.0
    assert MathExtension.wrap(361, 0, 360) == 1.0

    # Test with float values
    assert MathExtension.wrap(10.5, 0, 10) == 0.5
    assert MathExtension.wrap(370.5, 0, 360) == 10.5

    # Test with negative ranges
    assert MathExtension.wrap(-15, -10, 0) == -5.0
    assert MathExtension.wrap(5, -10, 0) == -5.0

    # Test with arbitrary ranges
    assert MathExtension.wrap(25, 10, 20) == 15.0
    assert MathExtension.wrap(5, 10, 20) == 15.0

    # Test with non-range
    assert MathExtension.wrap(5, 10, 10) == 10.0

    # Test error handling - invalid input types
    for case in (
        "{{ wrap('invalid', 0, 10) }}",
        "{{ wrap(5, 'invalid', 10) }}",
        "{{ wrap(5, 0, 'invalid') }}",
    ):
        with pytest.raises(TemplateError):
            render(hass, case)


def test_remap(hass: HomeAssistant) -> None:
    """Test remap function."""
    # Test function and filter usage in templates, with kitchen sink parameters.
    # We don't check the return value; that's covered by the unit tests below.
    assert render(hass, "{{ remap(5, 0, 6, 0, 740, steps=10) }}")
    assert render(hass, "{{ 50 | remap(0, 100, 0, 10, steps=8) }}")

    # Test basic remapping - scale from 0-10 to 0-100
    assert MathExtension.remap(0, 0, 10, 0, 100) == 0.0
    assert MathExtension.remap(5, 0, 10, 0, 100) == 50.0
    assert MathExtension.remap(10, 0, 10, 0, 100) == 100.0

    # Test with different input and output ranges
    assert MathExtension.remap(50, 0, 100, 0, 10) == 5.0
    assert MathExtension.remap(25, 0, 100, 0, 10) == 2.5

    # Test with negative ranges
    assert MathExtension.remap(0, -10, 10, 0, 100) == 50.0
    assert MathExtension.remap(-10, -10, 10, 0, 100) == 0.0
    assert MathExtension.remap(10, -10, 10, 0, 100) == 100.0

    # Test inverted output range
    assert MathExtension.remap(0, 0, 10, 100, 0) == 100.0
    assert MathExtension.remap(5, 0, 10, 100, 0) == 50.0
    assert MathExtension.remap(10, 0, 10, 100, 0) == 0.0

    # Test values outside input range, and edge modes
    assert MathExtension.remap(15, 0, 10, 0, 100, edges="none") == 150.0
    assert MathExtension.remap(-4, 0, 10, 0, 100, edges="none") == -40.0
    assert MathExtension.remap(15, 0, 10, 0, 80, edges="clamp") == 80.0
    assert MathExtension.remap(-5, 0, 10, -1, 1, edges="clamp") == -1
    assert MathExtension.remap(15, 0, 10, 0, 100, edges="wrap") == 50.0
    assert MathExtension.remap(-5, 0, 10, 0, 100, edges="wrap") == 50.0

    # Test sensor conversion use case: Celsius to Fahrenheit: 0-100°C to 32-212°F
    assert MathExtension.remap(0, 0, 100, 32, 212) == 32.0
    assert MathExtension.remap(100, 0, 100, 32, 212) == 212.0
    assert MathExtension.remap(50, 0, 100, 32, 212) == 122.0

    # Test time conversion use case: 0-60 minutes to 0-360 degrees, with wrap
    assert MathExtension.remap(80, 0, 60, 0, 360, edges="wrap") == 120.0

    # Test percentage to byte conversion (0-100% to 0-255)
    assert MathExtension.remap(0, 0, 100, 0, 255) == 0.0
    assert MathExtension.remap(50, 0, 100, 0, 255) == 127.5
    assert MathExtension.remap(100, 0, 100, 0, 255) == 255.0

    # Test with float precision
    assert MathExtension.remap(2.5, 0, 10, 0, 100) == 25.0
    assert MathExtension.remap(7.5, 0, 10, 0, 100) == 75.0

    # Test error handling
    for case in (
        "{{ remap(5, 10, 10, 0, 100) }}",
        "{{ remap('invalid', 0, 10, 0, 100) }}",
        "{{ remap(5, 'invalid', 10, 0, 100) }}",
        "{{ remap(5, 0, 'invalid', 0, 100) }}",
        "{{ remap(5, 0, 10, 'invalid', 100) }}",
        "{{ remap(5, 0, 10, 0, 'invalid') }}",
    ):
        with pytest.raises(TemplateError):
            render(hass, case)


def test_remap_with_steps(hass: HomeAssistant) -> None:
    """Test remap function with steps parameter."""
    # Test basic stepping - quantize to 10 steps
    assert MathExtension.remap(0.2, 0, 10, 0, 100, steps=10) == 0.0
    assert MathExtension.remap(5.3, 0, 10, 0, 100, steps=10) == 50.0
    assert MathExtension.remap(10, 0, 10, 0, 100, steps=10) == 100.0

    # Test stepping with intermediate values - should snap to nearest step
    # With 10 steps, normalized values are rounded: 0.0, 0.1, 0.2, ..., 1.0
    assert MathExtension.remap(2.4, 0, 10, 0, 100, steps=10) == 20.0
    assert MathExtension.remap(2.5, 0, 10, 0, 100, steps=10) == 20.0
    assert MathExtension.remap(2.6, 0, 10, 0, 100, steps=10) == 30.0

    # Test with 4 steps (0%, 25%, 50%, 75%, 100%)
    assert MathExtension.remap(0, 0, 10, 0, 100, steps=4) == 0.0
    assert MathExtension.remap(2.5, 0, 10, 0, 100, steps=4) == 25.0
    assert MathExtension.remap(5, 0, 10, 0, 100, steps=4) == 50.0
    assert MathExtension.remap(7.5, 0, 10, 0, 100, steps=4) == 75.0
    assert MathExtension.remap(10, 0, 10, 0, 100, steps=4) == 100.0

    # Test with 2 steps (0%, 50%, 100%)
    assert MathExtension.remap(2, 0, 10, 0, 100, steps=2) == 0.0
    assert MathExtension.remap(6, 0, 10, 0, 100, steps=2) == 50.0
    assert MathExtension.remap(8, 0, 10, 0, 100, steps=2) == 100.0

    # Test with 1 step (0%, 100%)
    assert MathExtension.remap(0, 0, 10, 0, 100, steps=1) == 0.0
    assert MathExtension.remap(5, 0, 10, 0, 100, steps=1) == 0.0
    assert MathExtension.remap(6, 0, 10, 0, 100, steps=1) == 100.0
    assert MathExtension.remap(10, 0, 10, 0, 100, steps=1) == 100.0

    # Test with inverted output range and steps
    assert MathExtension.remap(4.8, 0, 10, 100, 0, steps=4) == 50.0

    # Test with 0 or negative steps (should be ignored/no quantization)
    assert MathExtension.remap(5, 0, 10, 0, 100, steps=0) == 50.0
    assert MathExtension.remap(2.7, 0, 10, 0, 100, steps=0) == 27.0
    assert MathExtension.remap(5, 0, 10, 0, 100, steps=-1) == 50.0


def test_remap_with_mirror(hass: HomeAssistant) -> None:
    """Test the mirror edge mode of the remap function."""

    assert [
        MathExtension.remap(i, 0, 4, 0, 1, edges="mirror") for i in range(-4, 9)
    ] == [1.0, 0.75, 0.5, 0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0]

    # Test with different output range
    assert MathExtension.remap(15, 0, 10, 50, 150, edges="mirror") == 100.0
    assert MathExtension.remap(25, 0, 10, 50, 150, edges="mirror") == 100.0
    # Test with inverted output range
    assert MathExtension.remap(15, 0, 10, 100, 0, edges="mirror") == 50.0
    assert MathExtension.remap(12, 0, 10, 100, 0, edges="mirror") == 20.0
    # Test without remapping
    assert MathExtension.remap(-0.1, 0, 1, 0, 1, edges="mirror") == pytest.approx(0.1)
