"""Fixtures for the Victron Modbus tests."""

from collections.abc import Generator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.victron_modbus.const import DOMAIN

from . import SERIAL, VM_3P75CT, set_identity


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Keep config flow tests from setting up the integration."""
    with patch(
        "homeassistant.components.victron_modbus.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for a VM-3P75CT."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"VM-3P75CT ({SERIAL})",
        data={"host": "192.168.1.101", "model": "vm_3p75ct"},
        unique_id=SERIAL,
    )


@pytest.fixture
def mock_unit(mock_modbus_unit):
    """Point the runtime and config-flow Modbus helpers at a fake VM-3P75CT.

    ``mock_modbus_unit`` (from ``modbus_connection``'s own pytest plugin) is a
    real in-memory register simulator, so the actual device classes
    (``VM3P75CT``, ``VM3P5A``, ``P1Link``) run unmodified against it - no
    mocking of the device classes themselves is needed.
    """
    set_identity(mock_modbus_unit, VM_3P75CT)

    @asynccontextmanager
    async def _temporary_unit(*args, **kwargs):
        yield mock_modbus_unit

    with (
        patch(
            "homeassistant.components.victron_modbus.async_get_unit",
            return_value=mock_modbus_unit,
        ),
        patch(
            "homeassistant.components.victron_modbus.config_flow.async_get_temporary_unit",
            side_effect=_temporary_unit,
        ),
    ):
        yield mock_modbus_unit
