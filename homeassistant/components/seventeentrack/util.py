"""Utility helpers for 17Track."""

from aiohttp import CookieJar


def create_cookie_jar() -> CookieJar:
    """Create a cookie jar compatible with 17Track."""
    return CookieJar(quote_cookie=False)
