"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from datetime import datetime, timedelta
from http import HTTPStatus
import logging
import re
from typing import Any

import evohomeasync2 as evo

from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


def dt_local_to_aware(dt_naive: datetime) -> datetime:
    """Convert a local/naive datetime to TZ-aware."""
    dt_aware = dt_util.now() + (dt_naive - datetime.now())
    if dt_aware.microsecond >= 500000:
        dt_aware += timedelta(seconds=1)
    return dt_aware.replace(microsecond=0)


def dt_aware_to_naive(dt_aware: datetime) -> datetime:
    """Convert a TZ-aware datetime to naive/local."""
    dt_naive = datetime.now() + (dt_aware - dt_util.now())
    if dt_naive.microsecond >= 500000:
        dt_naive += timedelta(seconds=1)
    return dt_naive.replace(microsecond=0)


def convert_until(status_dict: dict, until_key: str) -> None:
    """Reformat a dt str from "%Y-%m-%dT%H:%M:%SZ" as local/aware/isoformat."""
    if until_key in status_dict and (  # only present for certain modes
        dt_utc_naive := dt_util.parse_datetime(status_dict[until_key])
    ):
        status_dict[until_key] = dt_util.as_local(dt_utc_naive).isoformat()


def convert_dict(dictionary: dict[str, Any]) -> dict[str, Any]:
    """Recursively convert a dict's keys to snake_case."""

    def convert_key(key: str) -> str:
        """Convert a string to snake_case."""
        string = re.sub(r"[\-\.\s]", "_", str(key))
        return (
            (string[0]).lower()
            + re.sub(
                r"[A-Z]",
                lambda matched: f"_{matched.group(0).lower()}",  # type:ignore[str-bytes-safe]
                string[1:],
            )
        )

    return {
        (convert_key(k) if isinstance(k, str) else k): (
            convert_dict(v) if isinstance(v, dict) else v
        )
        for k, v in dictionary.items()
    }


def handle_evo_exception(err: evo.RequestFailed) -> None:
    """Return False if the exception can't be ignored."""

    try:
        raise err

    except evo.AuthenticationFailed:
        _LOGGER.error(
            (
                "Failed to authenticate with the vendor's server. Check your username"
                " and password. NB: Some special password characters that work"
                " correctly via the website will not work via the web API. Message"
                " is: %s"
            ),
            err,
        )

    except evo.RequestFailed:
        if err.status is None:
            _LOGGER.warning(
                (
                    "Unable to connect with the vendor's server. "
                    "Check your network and the vendor's service status page. "
                    "Message is: %s"
                ),
                err,
            )

        elif err.status == HTTPStatus.SERVICE_UNAVAILABLE:
            _LOGGER.warning(
                "The vendor says their server is currently unavailable. "
                "Check the vendor's service status page"
            )

        elif err.status == HTTPStatus.TOO_MANY_REQUESTS:
            _LOGGER.warning(
                (
                    "The vendor's API rate limit has been exceeded. "
                    "If this message persists, consider increasing the %s"
                ),
                CONF_SCAN_INTERVAL,
            )

        else:
            raise  # we don't expect/handle any other Exceptions
