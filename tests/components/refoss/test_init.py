"""Tests for the Refoss integration setup."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.refoss.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import FakeDiscovery, build_base_device_mock

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entry_data", "device_ip", "expected_host", "expected_coordinators"),
    [
        pytest.param({}, "1.1.1.1", None, 1, id="broadcast"),
        pytest.param(
            {CONF_HOST: "192.0.2.10"},
            "192.0.2.10",
            "192.0.2.10",
            1,
            id="configured-host",
        ),
        pytest.param(
            {CONF_HOST: "192.0.2.10"},
            "192.0.2.20",
            "192.0.2.10",
            0,
            id="ignore-other-host",
        ),
    ],
)
async def test_setup_discovery_target(
    hass: HomeAssistant,
    entry_data: dict[str, str],
    device_ip: str,
    expected_host: str | None,
    expected_coordinators: int,
) -> None:
    """Test setup uses the configured discovery target."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)
    discovery = FakeDiscovery()
    discovery.mock_devices["abc"].inner_ip = device_ip

    with (
        patch(
            "homeassistant.components.refoss.refoss_discovery_server",
            return_value=discovery,
        ),
        patch(
            "homeassistant.components.refoss.bridge.async_build_base_device",
            return_value=build_base_device_mock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert discovery.last_host == expected_host
    assert len(entry.runtime_data.coordinators) == expected_coordinators
