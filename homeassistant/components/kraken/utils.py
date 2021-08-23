"""Utility functions for the kraken integration."""
from __future__ import annotations

from pykrakenapi.pykrakenapi import KrakenAPI


def get_tradable_asset_pairs(kraken_api: KrakenAPI) -> dict[str, str]:
    """Get a list of tradable asset pairs."""
    tradable_asset_pairs = {}
    asset_pairs_df = kraken_api.get_tradable_asset_pairs()
    for pair in zip(asset_pairs_df.index.values, asset_pairs_df["wsname"]):
        if not pair[0].endswith(
            ".d"
        ):  # Remove darkpools https://support.kraken.com/hc/en-us/articles/360001391906-Introducing-the-Kraken-Dark-Pool
            tradable_asset_pairs[pair[1]] = pair[0]
    return tradable_asset_pairs
