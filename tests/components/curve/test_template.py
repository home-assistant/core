"""Test Curve template functions."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError

from .conftest import MOCK_SEGMENTS, MOCK_STEP_SEGMENTS

from tests.helpers.template.helpers import render


@pytest.mark.parametrize(
    ("value_to_expected", "curve"),
    [
        ({5: 2.5, 15: 10, -5: 0, 25: 15}, MOCK_SEGMENTS),
        ({5: 0, 15: 5}, MOCK_STEP_SEGMENTS),
        ({5: 2.5}, [[0, 0, 10, 5, "linear"], [10, 5, 20, 15, "linear"]]),
    ],
)
async def test_curve_template(hass: HomeAssistant, value_to_expected, curve) -> None:
    """Test curve template function and filter."""

    for value, expected in value_to_expected.items():
        result = render(hass, f"{{{{ curve({value!r}, {curve!r}) }}}}")
        assert float(result) == expected
        result = render(hass, f"{{{{ {value!r}|curve({curve!r}) }}}}")
        assert float(result) == expected


async def test_curve_template_reference(hass: HomeAssistant, mock_config_entry) -> None:
    """Test curve template function referencing configured curve."""
    mock_config_entry.add_to_hass(hass)

    hass.states.async_set("sensor.test_source", "0")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Reference the curve by entity_id
    result = render(hass, "{{ curve(5, 'sensor.test_curve') }}")
    assert float(result) == 2.5


async def test_curve_template_with_default(hass: HomeAssistant) -> None:
    """Test curve template with default value."""
    result = render(
        hass, "{{ curve('invalid', segments, default=0) }}", {"segments": MOCK_SEGMENTS}
    )
    assert float(result) == 0.0
    result = render(hass, "{{ curve(5, 'nonexistent_id', default=42) }}")
    assert float(result) == 42.0


async def test_curve_template_invalid(hass: HomeAssistant) -> None:
    """Test curve template with various invalid states."""
    with pytest.raises(TemplateError):
        render(hass, "{{ curve('invalid', segments) }}", {"segments": MOCK_SEGMENTS})
    with pytest.raises(TemplateError, match="no_segments"):
        render(hass, "{{ curve(5, []) }}")
    with pytest.raises(TemplateError, match="invalid_segment_structure"):
        render(hass, '{{ curve(5, [{"x0": 0, "y0": 0}]) }}')
    with pytest.raises(TemplateError, match="not loaded"):
        render(hass, "{{ curve(5, 'nonexistent_id') }}")
    with pytest.raises(TemplateError, match="got invalid input"):
        render(hass, "{{ curve('not_a_number', segments) }}", {"segments": []})
    with pytest.raises(
        TemplateError, match="Second argument must be curve ID .* or segments"
    ):
        render(hass, "{{ curve(5, 123) }}")
