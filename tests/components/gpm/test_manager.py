"""Tests for GPM manager."""

import pytest


@pytest.mark.parametrize(
    ("repo_url", "unique_id"),
    [
        ("https://github.com/user/foo.git", "github_com.user.foo"),
        ("https://github.com/another-user/bar", "github_com.another_user.bar"),
        (
            "https://gitlab.com/YETanotherUser123/baz/",
            "gitlab_com.yetanotheruser123.baz",
        ),
        ("http://user:pass@example.com:1234/abc/", "example_com.abc"),
    ],
)
def test_unique_id(mock_integration_manager, repo_url, unique_id) -> None:
    """Test generating of unique_id for given repo_url."""
    mock_integration_manager.repo_url = repo_url
    assert mock_integration_manager.unique_id == unique_id
