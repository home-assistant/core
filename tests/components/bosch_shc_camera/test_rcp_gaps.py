"""Tests for rcp.py's `async_update_rcp_data` coordinator-cache merge wrapper."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bosch_shc_camera_client.rcp import RcpCameraData
import pytest

from homeassistant.components.bosch_shc_camera.rcp import async_update_rcp_data

CAM_ID = "cam-1"


def _make_coordinator() -> SimpleNamespace:
    return SimpleNamespace(
        hass=MagicMock(),
        rcp_session_cache={},
        rcp_session_locks={},
        _rcp_cmd_failures={},
        rcp_dimmer_cache={},
        rcp_privacy_cache={},
        rcp_clock_offset_cache={},
        rcp_lan_ip_cache={},
        rcp_product_name_cache={},
        rcp_bitrate_cache={},
        rcp_alarm_catalog_cache={},
        rcp_motion_zones_cache={},
        rcp_motion_coords_cache={},
        rcp_tls_cert_cache={},
        rcp_network_services_cache={},
        rcp_iva_catalog_cache={},
    )


@pytest.mark.asyncio
async def test_none_result_skips_all_cache_merges() -> None:
    """A failed RCP session open (None result) touches no cache dict."""
    coordinator = _make_coordinator()

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_ssl_context",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_session",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.fetch_rcp_camera_data",
            AsyncMock(return_value=None),
        ),
    ):
        await async_update_rcp_data(coordinator, CAM_ID, "proxy-host", "proxy-hash")

    assert coordinator.rcp_dimmer_cache == {}
    assert coordinator.rcp_privacy_cache == {}


@pytest.mark.asyncio
async def test_full_result_merges_every_field_into_its_cache() -> None:
    """Every non-None field on the returned RcpCameraData is merged into its cache dict."""
    coordinator = _make_coordinator()
    data = RcpCameraData(
        dimmer=42,
        privacy=True,
        clock_offset=1.5,
        lan_ip="192.0.2.10",
        product_name="Eyes Outdoor II",
        bitrate=4096,
        alarm_catalog=["intrusion"],
        motion_zones=[{"zone": 1}],
        motion_coords=[(0, 0)],
        tls_cert="cert-blob",
        network_services=["rtsp"],
        iva_catalog=["loitering"],
    )

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_ssl_context",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_session",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.fetch_rcp_camera_data",
            AsyncMock(return_value=data),
        ) as mock_fetch,
    ):
        await async_update_rcp_data(coordinator, CAM_ID, "proxy-host", "proxy-hash")

    assert coordinator.rcp_dimmer_cache == {CAM_ID: 42}
    assert coordinator.rcp_privacy_cache == {CAM_ID: True}
    assert coordinator.rcp_clock_offset_cache == {CAM_ID: 1.5}
    assert coordinator.rcp_lan_ip_cache == {CAM_ID: "192.0.2.10"}
    assert coordinator.rcp_product_name_cache == {CAM_ID: "Eyes Outdoor II"}
    assert coordinator.rcp_bitrate_cache == {CAM_ID: 4096}
    assert coordinator.rcp_alarm_catalog_cache == {CAM_ID: ["intrusion"]}
    assert coordinator.rcp_motion_zones_cache == {CAM_ID: [{"zone": 1}]}
    assert coordinator.rcp_motion_coords_cache == {CAM_ID: [(0, 0)]}
    assert coordinator.rcp_tls_cert_cache == {CAM_ID: "cert-blob"}
    assert coordinator.rcp_network_services_cache == {CAM_ID: ["rtsp"]}
    assert coordinator.rcp_iva_catalog_cache == {CAM_ID: ["loitering"]}
    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.args[5] == CAM_ID
    assert mock_fetch.call_args.args[6] == "proxy-host"
    assert mock_fetch.call_args.args[7] == "proxy-hash"


@pytest.mark.asyncio
async def test_all_none_fields_leave_caches_untouched() -> None:
    """A result whose fields are all None (nothing new fetched) merges nothing."""
    coordinator = _make_coordinator()
    coordinator.rcp_dimmer_cache[CAM_ID] = "stale-value"
    data = RcpCameraData(
        dimmer=None,
        privacy=None,
        clock_offset=None,
        lan_ip=None,
        product_name=None,
        bitrate=None,
        alarm_catalog=None,
        motion_zones=None,
        motion_coords=None,
        tls_cert=None,
        network_services=None,
        iva_catalog=None,
    )

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_ssl_context",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_session",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.fetch_rcp_camera_data",
            AsyncMock(return_value=data),
        ),
    ):
        await async_update_rcp_data(coordinator, CAM_ID, "proxy-host", "proxy-hash")

    # Untouched: the pre-existing stale value survives since nothing new arrived.
    assert coordinator.rcp_dimmer_cache == {CAM_ID: "stale-value"}
    assert coordinator.rcp_privacy_cache == {}


@pytest.mark.asyncio
async def test_missing_cmd_failures_attr_defaults_to_empty_dict() -> None:
    """A coordinator without a pre-existing `_rcp_cmd_failures` attr still works."""
    coordinator = _make_coordinator()
    del coordinator._rcp_cmd_failures

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_ssl_context",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.async_get_bosch_cloud_session",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.rcp.fetch_rcp_camera_data",
            AsyncMock(return_value=None),
        ) as mock_fetch,
    ):
        await async_update_rcp_data(coordinator, CAM_ID, "proxy-host", "proxy-hash")

    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.args[4] == {}
