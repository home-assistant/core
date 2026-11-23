"""Tests for Daikin Onecta diagnostics."""

from hashlib import sha256
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta import OnectaConnectionError, Site
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.discovery_flow import DiscoveryKey

from .platform_helpers import _async_setup_fixture


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test cached cloud data is provided with identifying data redacted."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    hass.config_entries.async_update_entry(
        config_entry,
        title="Private account name",
        discovery_keys=MappingProxyType(
            {
                "_https._tcp.local.": (
                    DiscoveryKey(
                        domain="_https._tcp.local.",
                        key="altherma4-private-serial._https._tcp.local.",
                        version=1,
                    ),
                ),
            }
        ),
    )
    coordinator = config_entry.runtime_data
    coordinator.client.get_gateway_devices = AsyncMock()
    coordinator.client.get_sites = AsyncMock(
        return_value=[
            Site(
                id="site-1",
                name="Home",
                gateway_device_ids=[
                    device.id
                    for device in (config_entry.runtime_data.data or {}).values()
                ],
            )
        ]
    )

    with patch(
        "homeassistant.components.daikin_onecta.diagnostics.secrets.token_bytes",
        side_effect=[b"first diagnostic salt", b"second diagnostic salt"],
    ):
        diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry
        )
        second_diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry
        )

    assert diagnostics["config_entry"]["data"]["token"] == REDACTED
    assert diagnostics["config_entry"]["title"] == REDACTED
    assert diagnostics["config_entry"]["discovery_keys"] == REDACTED
    assert diagnostics["devices"]
    assert diagnostics["devices"][0]["id"] == REDACTED
    gateway = next(
        point
        for point in diagnostics["devices"][0]["management_points"]
        if point["management_point_type"] == "gateway"
    )
    assert gateway["characteristics"]["ipAddress"] == REDACTED
    assert diagnostics["sites"]["data"][0]["id"] == REDACTED
    assert diagnostics["sites"]["data"][0]["name"] == REDACTED
    gateway_id = next(iter(coordinator.data))
    assert diagnostics["sites"]["gateway_membership"][0] == {
        "gateway_id_hash": sha256(
            b"first diagnostic salt" + gateway_id.encode()
        ).hexdigest()[:8],
        "linked_to_site": True,
    }
    assert (
        diagnostics["sites"]["gateway_membership"][0]["gateway_id_hash"]
        != second_diagnostics["sites"]["gateway_membership"][0]["gateway_id_hash"]
    )
    assert gateway_id not in repr(diagnostics["sites"])
    coordinator.client.get_sites.assert_awaited_once_with()
    coordinator.client.get_gateway_devices.assert_not_awaited()


async def test_diagnostics_redacts_gateway_ssids(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Redact gateway Wi-Fi names from cached cloud data."""
    await _async_setup_fixture(hass, config_entry, "climate_floorheatingairflow")
    coordinator = config_entry.runtime_data
    coordinator.client.get_gateway_devices = AsyncMock()
    coordinator.client.get_sites = AsyncMock(return_value=[])

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    gateways = [
        point
        for device in diagnostics["devices"]
        for point in device["management_points"]
        if point["management_point_type"] == "gateway"
    ]
    assert gateways
    for gateway in gateways:
        characteristics = gateway["characteristics"]
        assert characteristics["ssid"] == REDACTED
        assert characteristics["wifiConnectionSSID"] == REDACTED


async def test_diagnostics_redacts_serialized_product_identifiers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Redact the serialized identifier of an Altherma management point."""
    await _async_setup_fixture(hass, config_entry, "altherma_firmwareupdate")
    config_entry.runtime_data.client.get_sites = AsyncMock(return_value=[])

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    point = next(
        point
        for device in diagnostics["devices"]
        for point in device["management_points"]
        if "sgtin" in point["characteristics"]
    )
    assert point["characteristics"]["sgtin"] == REDACTED


@pytest.mark.parametrize(
    "error",
    [
        OnectaConnectionError(
            "private network details", method="GET", path="/v1/sites"
        ),
        OAuth2TokenRequestReauthError(
            domain="daikin_onecta",
            request_info=MagicMock(),
            status=401,
            message="private token details",
        ),
        OAuth2TokenRequestConnectionError(domain="daikin_onecta"),
        TimeoutError("private timeout details"),
    ],
)
async def test_diagnostics_reports_site_lookup_failures(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Keep diagnostics available when the explicit Sites lookup fails."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    config_entry.runtime_data.client.get_sites = AsyncMock(side_effect=error)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["sites"]["error"] == {
        "type": type(error).__name__,
        "status": getattr(error, "status", None),
    }
    assert diagnostics["devices"]
    assert "private" not in str(diagnostics)


async def test_diagnostics_reports_oauth_token_failure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Include OAuth token refresh failures in diagnostics instead of returning 500."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    config_entry.runtime_data.client.get_sites = AsyncMock(
        side_effect=OAuth2TokenRequestError(
            domain="daikin_onecta",
            request_info=MagicMock(),
            status=401,
            message="private token details",
        )
    )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["sites"] == snapshot
    assert diagnostics["sites"] == {
        "error": {"type": "OAuth2TokenRequestError", "status": 401}
    }
