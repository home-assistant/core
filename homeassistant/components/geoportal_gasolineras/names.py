"""Readable names for fuel stations."""

import re

from aioprecioscarburantes import Station

# The Ministry lists "Roda de Andalucía (La)"; people say "La Roda de Andalucía"
_TRAILING_ARTICLE = re.compile(r"^(?P<name>.+?)\s*\((?P<article>[^)]+)\)$")


def municipality_name(municipality: str) -> str:
    """Move a trailing article in brackets to the front."""
    if match := _TRAILING_ARTICLE.match(municipality.strip()):
        article = match["article"]
        separator = "" if article.endswith("'") else " "
        return f"{article}{separator}{match['name']}"
    return municipality.strip()


def brand_name(brand: str) -> str:
    """Return the brand in title case, keeping short acronyms such as BP."""
    brand = brand.strip()
    return brand if len(brand) <= 3 else brand.title()


def clean_address(address: str) -> str:
    """Return the address in title case, without repeated spaces or commas."""
    return " ".join(address.split()).strip(" ,").title()


def station_name(station: Station, taken: set[str]) -> str:
    """Return brand and municipality, adding the address if the name is taken."""
    brand = brand_name(station.brand)
    municipality = municipality_name(station.municipality)
    # Some brands already include the town, such as "GAFISUR ANTEQUERA"
    name = (
        brand
        if municipality.casefold() in brand.casefold()
        else f"{brand} {municipality}"
    )
    if name in taken:
        name = f"{name} ({clean_address(station.address)})"
    return name
