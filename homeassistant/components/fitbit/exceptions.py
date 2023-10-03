"""Exceptions for fitbit API calls.

These exceptions exist to provide common exceptions for the async and sync client libraries.
"""


class FitbitApiException(Exception):
    """Error talking to the fitbit API."""


class FitbitAuthException(FitbitApiException):
    """Authentication related error talking to the fitbit API."""
