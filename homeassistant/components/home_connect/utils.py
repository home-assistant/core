"""Utility functions for Home Connect."""

import re

from aiohomeconnect.model.error import HomeConnectError

RE_CAMEL_CASE = re.compile(r"(?<!^)(?=[A-Z])|(?=\d)(?<=\D)")

# Unlike RE_CAMEL_CASE, this keeps acronyms and dimensions together, so that
# `XLCoffee` and `3DHotAir` become `XL Coffee` and `3D Hot Air` instead of
# `X L Coffee` and `3 D Hot Air`.
RE_ACRONYM_AWARE_CAMEL_CASE = re.compile(
    r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z\d])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)"
)


def get_dict_from_home_connect_error(
    err: HomeConnectError,
) -> dict[str, str]:
    """Return a translation string from a Home Connect error."""
    return {"error": str(err)}


def bsh_key_to_translation_key(bsh_key: str) -> str:
    """Convert a BSH key to a translation key format.

    This function takes a BSH key, such as `Dishcare.Dishwasher.Program.Eco50`,
    and converts it to a translation key format, such as
    `dishcare_dishwasher_bsh_key_eco50`.
    """
    return "_".join(
        RE_CAMEL_CASE.sub("_", split) for split in bsh_key.split(".")
    ).lower()


def program_key_to_readable_name(program_key: str) -> str:
    """Return a human-readable name derived from a raw program key.

    This function takes a program key, such as
    `ConsumerProducts.CoffeeMaker.Program.Beverage.Ristretto`, and converts its
    last segment into a human-readable string, such as `Ristretto`.

    Favorites, such as `BSH.Common.Program.Favorite.001`, keep the `Favorite`
    segment too, e.g. `Favorite 001`, since the trailing number alone would
    not be descriptive.

    Acronyms and dimensions are kept as one word, so `XLCoffee` becomes
    `XL Coffee` and `3DHotAir` becomes `3D Hot Air`.
    """
    segments = program_key.split(".")
    name_segments = segments[-2:] if segments[-2:-1] == ["Favorite"] else segments[-1:]
    return " ".join(
        RE_ACRONYM_AWARE_CAMEL_CASE.sub(" ", segment) for segment in name_segments
    )
