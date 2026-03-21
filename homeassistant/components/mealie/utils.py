"""Mealie util functions."""

from __future__ import annotations

from awesomeversion import AwesomeVersion


def create_version(version: str) -> AwesomeVersion:
    """Convert beta versions to PEP440."""
    return AwesomeVersion(version.replace("beta-", "b"))


def mealie_recipe_image_url(host: str, recipe_id: str) -> str:
    """Build the Mealie media URL for a recipe image."""
    return f"{host}/api/media/recipes/{recipe_id}/images/original.webp"
