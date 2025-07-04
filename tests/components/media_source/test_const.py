"""Test constants for the media source component."""

import pytest

from homeassistant.components.media_source.const import URI_SCHEME_REGEX


@pytest.mark.parametrize(
    ("uri", "expected_domain", "expected_identifier"),
    [
        ("media-source://", None, None),
        ("media-source://local_media", "local_media", None),
        (
            "media-source://local_media/some/path/file.mp3",
            "local_media",
            "some/path/file.mp3",
        ),
        ("media-source://a/b", "a", "b"),
        (
            "media-source://domain/file with spaces.mp4",
            "domain",
            "file with spaces.mp4",
        ),
        (
            "media-source://domain/file-with-dashes.mp3",
            "domain",
            "file-with-dashes.mp3",
        ),
        ("media-source://domain/file.with.dots.mp3", "domain", "file.with.dots.mp3"),
        (
            "media-source://domain/special!@#$%^&*()chars",
            "domain",
            "special!@#$%^&*()chars",
        ),
    ],
)
def test_valid_uri_patterns(
    uri: str, expected_domain: str | None, expected_identifier: str | None
) -> None:
    """Test various valid URI patterns."""
    match = URI_SCHEME_REGEX.match(uri)
    assert match is not None
    assert match.group("domain") == expected_domain
    assert match.group("identifier") == expected_identifier


@pytest.mark.parametrize(
    "domain",
    [
        "_test",  # starts with underscore
        "test_",  # ends with underscore
        "_test_",  # starts and ends with underscore
        "_",  # single underscore
        "test-123",  # contains hyphen
        "test.123",  # contains dot
        "test 123",  # contains space
        "TEST",  # uppercase letters
        "Test",  # mixed case
    ],
)
def test_invalid_domain_names(domain: str) -> None:
    """Test invalid domain names that should not match."""
    match = URI_SCHEME_REGEX.match(f"media-source://{domain}")
    assert match is None, f"Domain '{domain}' should be invalid"


def test_identifier_cannot_start_with_slash():
    """Test that identifiers cannot start with forward slash."""
    # This should not match because identifier starts with /
    match = URI_SCHEME_REGEX.match("media-source://domain//invalid")
    assert match is None


@pytest.mark.parametrize(
    "uri",
    [
        "media-source:",  # missing //
        "media-source:/",  # missing second /
        "media-source:///",  # extra /
        "media-source://domain/",  # trailing slash after domain
        "invalid-scheme://domain",  # wrong scheme
        "media-source//domain",  # missing :
        "MEDIA-SOURCE://domain",  # uppercase scheme
        "media_source://domain",  # underscore in scheme
        "",  # empty string
        "media-source",  # scheme only
        "media-source://domain extra",  # extra content
        "prefix media-source://domain",  # prefix content
        "media-source://domain suffix",  # suffix content
    ],
)
def test_invalid_uris(uri: str) -> None:
    """Test invalid URI formats."""
    match = URI_SCHEME_REGEX.match(uri)
    assert match is None, f"URI '{uri}' should be invalid"
