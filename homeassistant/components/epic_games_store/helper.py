"""Helper for Epic Games Store."""
from typing import Any


def get_country_from_locale(locale: str) -> str:
    """Get the country code from locale."""
    excepts = {"ja": "JP", "ko": "KR", "zh-Hant": "CN"}
    return (
        excepts[locale]
        if excepts.get(locale)
        else (locale[3:] if ("-" in locale) else locale)
    ).upper()


def is_free_game(game: dict[str, Any]) -> bool:
    """Return if the game is free or will be free."""
    return (
        # Current free game(s)
        game["promotions"]["promotionalOffers"]
        and game["promotions"]["promotionalOffers"][0]["promotionalOffers"][0][
            "discountSetting"
        ]["discountPercentage"]
        == 0
        and
        # Checking current price, maybe not necessary
        game["price"]["totalPrice"]["discountPrice"] == 0
    ) or (
        # Upcoming free game(s)
        game["promotions"]["upcomingPromotionalOffers"]
        and game["promotions"]["upcomingPromotionalOffers"][0]["promotionalOffers"][0][
            "discountSetting"
        ]["discountPercentage"]
        == 0
    )
