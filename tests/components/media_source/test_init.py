"""Test Media Source initialization."""

from homeassistant.components import media_source


async def test_is_media_source_id() -> None:
    """Test media source validation."""
    assert media_source.is_media_source_id(media_source.URI_SCHEME)
    assert media_source.is_media_source_id(f"{media_source.URI_SCHEME}domain")
    assert media_source.is_media_source_id(
        f"{media_source.URI_SCHEME}domain/identifier"
    )
    assert not media_source.is_media_source_id("test")


async def test_generate_media_source_id() -> None:
    """Test identifier generation."""
    tests = [
        (None, None),
        (None, ""),
        ("", ""),
        ("domain", None),
        ("domain", ""),
        ("domain", "identifier"),
    ]

    for domain, identifier in tests:
        assert media_source.is_media_source_id(
            media_source.generate_media_source_id(domain, identifier)
        )
