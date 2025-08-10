"""Test ViCare utils."""

import pytest

from homeassistant.components.vicare.utils import filter_state


@pytest.mark.parametrize(
    ("state", "expected_result"),
    [
        (None, None),
        ("unknown", None),
        ("nothing", None),
        ("levelOne", "levelOne"),
    ],
)
async def test_filter_state(
    state: str | None,
    expected_result: str | None,
) -> None:
    """Test filter_state."""

    assert filter_state(state) == expected_result
