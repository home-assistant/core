"""Helper for Epic Games Store."""

import contextlib
from typing import Any

from homeassistant.util import dt as dt_util


def format_game_data(raw_game_data: dict[str, Any], language: str) -> dict[str, Any]:
    """Format raw API game data for Home Assistant users."""
    img_portrait = None
    img_landscape = None

    for image in raw_game_data["keyImages"]:
        if image["type"] == "OfferImageTall":
            img_portrait = image["url"]
        if image["type"] == "OfferImageWide":
            img_landscape = image["url"]

    current_promotions = raw_game_data["promotions"]["promotionalOffers"]
    upcoming_promotions = raw_game_data["promotions"]["upcomingPromotionalOffers"]

    promotion_data = {}
    if (
        current_promotions
        and raw_game_data["price"]["totalPrice"]["discountPrice"] == 0
    ):
        promotion_data = current_promotions[0]["promotionalOffers"][0]
    else:
        promotion_data = (current_promotions or upcoming_promotions)[0][
            "promotionalOffers"
        ][0]

    return {
        "title": raw_game_data["title"].replace("\xa0", " "),
        "description": raw_game_data["description"].strip().replace("\xa0", " "),
        "released_at": dt_util.parse_datetime(raw_game_data["effectiveDate"]),
        "original_price": raw_game_data["price"]["totalPrice"]["fmtPrice"][
            "originalPrice"
        ].replace("\xa0", " "),
        "publisher": raw_game_data["seller"]["name"],
        "url": get_game_url(raw_game_data, language),
        "img_portrait": img_portrait,
        "img_landscape": img_landscape,
        "discount_type": ("free" if is_free_game(raw_game_data) else "discount")
        if promotion_data
        else None,
        "discount_start_at": dt_util.parse_datetime(promotion_data["startDate"])
        if promotion_data
        else None,
        "discount_end_at": dt_util.parse_datetime(promotion_data["endDate"])
        if promotion_data
        else None,
    }


def get_game_url(raw_game_data: dict[str, Any], language: str) -> str:
    """Format raw API game data for Home Assistant users."""
    url_bundle_or_product = "bundles" if raw_game_data["offerType"] == "BUNDLE" else "p"
    url_slug: str | None = None
    try:
        url_slug = raw_game_data["offerMappings"][0]["pageSlug"]
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            url_slug = raw_game_data["catalogNs"]["mappings"][0]["pageSlug"]

    if not url_slug:
        url_slug = raw_game_data["productSlug"]

    return f"https://store.epicgames.com/{language}/{url_bundle_or_product}/{url_slug}"


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
