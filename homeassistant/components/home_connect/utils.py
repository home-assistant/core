"""Utility functions for Home Connect."""

import re

from aiohomeconnect.model.error import HomeConnectError

RE_CAMEL_CASE = re.compile(r"(?<!^)(?=[A-Z])|(?=\d)(?<=\D)")


def get_dict_from_home_connect_error(
    err: HomeConnectError,
) -> dict[str, str]:
    """Return a translation string from a Home Connect error."""
    return {"error": str(err)}


def bsh_key_to_translation_key(bsh_key: str) -> str:
    """Convert a BSH key to a translation key format.

    This function takes a BSH key, such as `Dishcare.Dishwasher.Program.Eco50`,
    and converts it to a translation key format, such as `dishcare_dishwasher_bsh_key_eco50`.
    """
    return "_".join(
        RE_CAMEL_CASE.sub("_", split) for split in bsh_key.split(".")
    ).lower()
