"""Utility functions for Home Connect."""

import re

from aiohomeconnect.model.error import HomeConnectError

from homeassistant.exceptions import HomeAssistantError

RE_CAMEL_CASE = re.compile(r"(?<!^)(?=[A-Z])|(?=\d)(?<=\D)")


def get_dict_from_home_connect_error(
    err: HomeConnectError,
) -> dict[str, str]:
    """Return a translation string from a Home Connect error."""
    return {"error": str(err)}


def raise_service_error(
    err: HomeConnectError,
    translation_key: str,
    extra_placeholders: dict[str, str] | None = None,
) -> None:
    """Raise a Home Assistant error with a translation string from a Home Connect error."""
    from .const import DOMAIN  # noqa: PLC0415 - avoid circular import

    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders={"error": str(err)} | (extra_placeholders or {}),
    ) from err


def bsh_key_to_translation_key(bsh_key: str) -> str:
    """Convert a BSH key to a translation key format.

    This function takes a BSH key, such as `Dishcare.Dishwasher.Program.Eco50`,
    and converts it to a translation key format, such as
    `dishcare_dishwasher_bsh_key_eco50`.
    """
    return "_".join(
        RE_CAMEL_CASE.sub("_", split) for split in bsh_key.split(".")
    ).lower()
