"""Typings for the xiaomi_miio integration."""

from typing import NamedTuple

import voluptuous as vol


class ServiceMethodDetails(NamedTuple):
    """Details for SERVICE_TO_METHOD mapping."""

    method: str
    schema: vol.Schema | None = None
