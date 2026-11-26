"""Tests for the Microsoft Text-to-Speech integration."""

from http import HTTPStatus

from requests import Response
from requests.exceptions import HTTPError


def http_error(status: HTTPStatus) -> HTTPError:
    """Return an HTTP error for a response with the given status."""
    response = Response()
    response.status_code = status
    return HTTPError(response=response)
