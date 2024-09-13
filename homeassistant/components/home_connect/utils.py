"""Utilities for Home Connect."""

from stringcase import pascalcase, snakecase


def bsh_key_to_translation_key(bsh_key: str) -> str:
    """Convert a BSH key to a translation key."""
    return snakecase(bsh_key).replace("__", "-").replace("b_s_h", "bsh")


def translation_key_to_bsh_key(translation_key: str) -> str:
    """Convert a translation key to a BSH key."""
    return pascalcase(
        translation_key.replace("bsh", "b_s_h").replace("-", "__")
    ).replace("_", ".")
