"""webOS Smart TV triggers."""
from __future__ import annotations

from typing import Protocol

import voluptuous as vol


class TriggersPlatformModule(Protocol):
    """Protocol type for the triggers platform."""

    TRIGGER_SCHEMA: vol.Schema
