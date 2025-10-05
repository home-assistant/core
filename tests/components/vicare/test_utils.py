"""Test ViCare utils."""

import pytest

from homeassistant.components.vicare.utils import filter_state, format_zigbee


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


@pytest.mark.parametrize(
    ("ieee", "expected_result"),
    [
        ("anything", "anything"),
        ("1234567812345678", "12:34:56:78:12:34:56:78"),
        ("12:34:56:78:12:34:56:78", "12:34:56:78:12:34:56:78"),
    ],
)
async def test_format_zigbee(
    ieee: str | None,
    expected_result: str | None,
) -> None:
    """Test format_zigbee."""

    assert format_zigbee(ieee) == expected_result
