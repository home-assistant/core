"""Constants for the Maico integration."""

from __future__ import annotations

import httpx

DOMAIN = "maico"

CONNECTION_ERRORS = (KeyError, httpx.HTTPError)
