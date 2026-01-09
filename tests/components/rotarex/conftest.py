"""Test stubs for rotarex_dimes_srg_api dependency."""

import sys
import types
from typing import Any

mod = types.ModuleType("rotarex_dimes_srg_api")


class InvalidAuth(Exception):
    """Auth error placeholder for tests."""


class RotarexApi:
    """Minimal stub for Rotarex API used by config_flow imports."""

    async def login(self, email: str, password: str) -> Any:  # pragma: no cover
        """Simulate user login."""
        return None


mod.InvalidAuth = InvalidAuth
mod.RotarexApi = RotarexApi

# Inject stub into sys.modules so imports succeed during tests
sys.modules["rotarex_dimes_srg_api"] = mod
