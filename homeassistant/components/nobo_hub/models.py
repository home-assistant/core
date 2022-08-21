"""The nobo_hub integration models."""
from __future__ import annotations

from dataclasses import dataclass

from pynobo import nobo

from homeassistant.core import CALLBACK_TYPE


@dataclass
class NoboHubData:
    """Data for the nobo_hub integration."""

    hub: nobo
    remove_listener: CALLBACK_TYPE
