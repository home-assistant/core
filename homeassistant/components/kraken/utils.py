"""Utility functions for the kraken integration."""
from typing import Dict

from pykrakenapi.pykrakenapi import KrakenAPI


def get_tradable_asset_pairs(kraken_api: KrakenAPI) -> Dict[str, str]:
    """Get a list of tradable asset pairs."""
    tradable_asset_pairs = {}
    asset_pairs_df = kraken_api.get_tradable_asset_pairs()
    for pair in zip(asset_pairs_df.index.values, asset_pairs_df["wsname"]):
        try:
            if ".d" not in pair[0]:  # Remove strange duplicates
                tradable_asset_pairs[pair[1]] = pair[0]
        except AttributeError:
            # Ignore NaN
            pass
    return tradable_asset_pairs
