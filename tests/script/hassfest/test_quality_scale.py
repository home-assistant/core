"""Tests for the quality scale validation."""

import pytest

from script.hassfest.quality_scale import PULL_REQUEST_REFERENCE


@pytest.mark.parametrize(
    "comment",
    [
        "See https://github.com/home-assistant/core/pull/134027",
        "https://github.com/home-assistant/brands/pull/11326#discussion_r1",
        "The icon is in home-assistant/brands#11237.",
        "Will be fixed in PR #147064.",
        "Future enhancements. PR 153958",
        "Will be fixed in #12345.",
    ],
)
def test_pull_request_reference_found(comment: str) -> None:
    """Test comments that refer to a pull request are found."""
    assert PULL_REQUEST_REFERENCE.search(comment)


@pytest.mark.parametrize(
    "comment",
    [
        "Reauthentication will be added in a follow-up PR.",
        "Blocked by https://github.com/home-assistant/core/issues/123456",
        "The device supports channels 1 to 13 and Wi-Fi 802.11#5.",
        "The light reports the color #fff when off.",
        "The API returns at most 100 items.",
    ],
)
def test_pull_request_reference_not_found(comment: str) -> None:
    """Test comments without a pull request reference are allowed."""
    assert not PULL_REQUEST_REFERENCE.search(comment)
