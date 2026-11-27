"""Tests for the jellyfin integration."""

from typing import Any

from pytest_homeassistant.common import load_json_value_fixture

from homeassistant.core import HomeAssistant


def load_json_fixture(filename: str) -> Any:
    """Load JSON fixture on-demand."""
    return load_json_value_fixture(f"jellyfin/{filename}")


async def async_load_json_fixture(hass: HomeAssistant, filename: str) -> Any:
    """Load JSON fixture on-demand asynchronously."""
    return await hass.async_add_executor_job(load_json_fixture, filename)
