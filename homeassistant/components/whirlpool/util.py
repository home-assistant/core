"""Utility functions for the Whirlpool Sixth Sense integration."""

from whirlpool.backendselector import Brand, Region


def get_brand_for_region(region: Region) -> Brand:
    """Get the correct brand for each region."""
    return Brand.Maytag if region == Region.US else Brand.Whirlpool
