"""Helpers for Collection image integration."""


def content_type_is_image(media_content_type: str) -> bool:
    """Check if the media item is an image."""

    return media_content_type.startswith("image")
