"""Helpers for the Microsoft Text-to-Speech integration."""

from http import HTTPStatus

from requests.exceptions import HTTPError, RequestException


def is_unauthorized(err: RequestException) -> bool:
    """Return if the service rejected the API key for the region."""
    return (
        isinstance(err, HTTPError)
        and err.response is not None
        and err.response.status_code == HTTPStatus.UNAUTHORIZED
    )
