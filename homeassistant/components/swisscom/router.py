"""Represent the Swisscom router and its devices."""
from __future__ import annotations

from sc_inetbox_adapter import InternetboxAdapter

from .errors import CannotLoginException


def get_api(
    password: str,
    host: str,
    ssl: bool
) -> InternetboxAdapter:
    """Get the Internetbox API and login to it."""
    api: InternetboxAdapter = InternetboxAdapter(password, ssl, host)

    if api.create_session() != http.HTTPStatus.OK:
        raise CannotLoginException

    return api
