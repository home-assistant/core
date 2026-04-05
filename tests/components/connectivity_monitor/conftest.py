"""Common fixtures for the Connectivity Monitor tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.connectivity_monitor.const import (
    CONF_DNS_SERVER,
    CONF_HOST,
    CONF_INTERVAL,
    CONF_PROTOCOL,
    CONF_TARGETS,
    DEFAULT_DNS_SERVER,
    DOMAIN,
    PROTOCOL_ICMP,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override config entry setup during config flow tests."""
    with (
        patch(
            "homeassistant.components.connectivity_monitor.async_setup_entry",
            return_value=True,
        ) as mock_entry_setup,
        patch(
            "homeassistant.components.connectivity_monitor.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock_entry_setup


@pytest.fixture
def network_target() -> dict[str, str]:
    """Return a basic network target."""
    return {
        CONF_HOST: "192.168.1.1",
        CONF_PROTOCOL: PROTOCOL_ICMP,
        "device_name": "Router",
    }


@pytest.fixture
def network_config_entry(network_target: dict[str, str]) -> MockConfigEntry:
    """Return a network config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={
            CONF_TARGETS: [network_target],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
