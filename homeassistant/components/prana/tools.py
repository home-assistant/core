"""Utility helpers for the Prana integration."""


class Tools:
    """Collection of static helper methods."""

    @staticmethod
    def hex_string_to_int_list(hex_str: str) -> list[int]:
        """Convert a hex string (optionally containing spaces) into a list of ints."""
        hex_str = hex_str.replace(" ", "").strip()
        return [int(hex_str[i : i + 2], 16) for i in range(0, len(hex_str), 2)]
