"""Tests for STIPS local HTTP host resolution helpers."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.stips_iru1 import local_http
from homeassistant.core import HomeAssistant


def test_iter_dns_host_candidates_rejects_invalid_catalog_host() -> None:
    """Invalid cloud-provided unique names should not become request hosts."""
    hosts = local_http.iter_dns_host_candidates("http://evil/path", "10.0.0.42")

    assert hosts == ["10.0.0.42"]


def test_iter_dns_host_candidates_accepts_valid_catalog_host() -> None:
    """Valid unique-name host should produce DNS-first candidates."""
    hosts = local_http.iter_dns_host_candidates("stips-iru1-98eea1", "")

    assert hosts == ["stips-iru1-98eea1", "stips-iru1-98eea1.local"]


async def test_async_build_control_hosts_uses_short_ttl_cache(
    hass: HomeAssistant,
) -> None:
    """Second lookup with same key should use cache without probing again."""
    local_http._HOST_CACHE.clear()

    with patch(
        "homeassistant.components.stips_iru1.local_http.async_fetch_device_info_live_ip",
        new=AsyncMock(return_value="10.0.0.123"),
    ) as mock_probe:
        first_hosts, first_live_ip = await local_http.async_build_control_hosts(
            hass,
            device_unique_name="stips-iru1-98eea1",
            backend_ip="",
        )
        second_hosts, second_live_ip = await local_http.async_build_control_hosts(
            hass,
            device_unique_name="stips-iru1-98eea1",
            backend_ip="",
        )

    assert first_live_ip == "10.0.0.123"
    assert second_live_ip == "10.0.0.123"
    assert first_hosts == second_hosts
    assert mock_probe.await_count == 1
