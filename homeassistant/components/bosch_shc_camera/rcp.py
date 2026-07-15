"""Bosch RCP (Remote Configuration Protocol) coordinator-cache orchestration.

The actual RCP fetch (session management, protocol reads, response parsing)
lives in `bosch_shc_camera_client.rcp.fetch_rcp_camera_data` now
(Core-submission client-library extraction, see
knowledge-base/ha-core-submission-plan.md task #11). This module is the thin
HA-integration-specific wrapper: it builds the session/ssl-context the
library needs, calls the pure fetch, and merges the returned `RcpCameraData`
fields into the coordinator's own cache dicts.
"""

from __future__ import annotations

import logging
from typing import Any

from bosch_shc_camera_client.rcp import fetch_rcp_camera_data

from .cloud_ssl import (
    async_get_bosch_cloud_session,
    async_get_bosch_cloud_ssl_context,
)

_LOGGER = logging.getLogger(__name__)

__all__ = ["async_update_rcp_data"]


async def async_update_rcp_data(
    coordinator: Any,
    cam_id: str,
    proxy_host: str,
    proxy_hash: str,
) -> None:
    """Fetch RCP data (LED dimmer, privacy state, etc.) for a camera via cloud proxy.

    Merges the fetch result into the coordinator's own cache dicts. Gracefully
    skips on any failure -- RCP is read-only supplementary data and must never
    block the main coordinator update.

    Expects the coordinator to have these dict attributes:
      - _rcp_session_cache
      - _rcp_dimmer_cache
      - _rcp_privacy_cache
      - _rcp_clock_offset_cache
      - _rcp_lan_ip_cache
      - _rcp_product_name_cache
      - _rcp_bitrate_cache
      - _rcp_alarm_catalog_cache
      - _rcp_motion_zones_cache
      - _rcp_motion_coords_cache
      - _rcp_tls_cert_cache
      - _rcp_network_services_cache
      - _rcp_iva_catalog_cache
      - _rcp_cmd_failures
      - _rcp_session_locks
      - hass
    """
    ssl_context = await async_get_bosch_cloud_ssl_context(coordinator.hass)
    session = await async_get_bosch_cloud_session(coordinator.hass)
    failures = getattr(coordinator, "_rcp_cmd_failures", {}).setdefault(cam_id, {})

    data = await fetch_rcp_camera_data(
        session,
        ssl_context,
        coordinator.rcp_session_cache,
        coordinator.rcp_session_locks,
        failures,
        cam_id,
        proxy_host,
        proxy_hash,
    )
    if data is None:
        _LOGGER.debug(
            "async_update_rcp_data: could not open RCP session for %s", cam_id
        )
        return

    if data.dimmer is not None:
        coordinator.rcp_dimmer_cache[cam_id] = data.dimmer
    if data.privacy is not None:
        coordinator.rcp_privacy_cache[cam_id] = data.privacy
    if data.clock_offset is not None:
        coordinator.rcp_clock_offset_cache[cam_id] = data.clock_offset
    if data.lan_ip is not None:
        coordinator.rcp_lan_ip_cache[cam_id] = data.lan_ip
    if data.product_name is not None:
        coordinator.rcp_product_name_cache[cam_id] = data.product_name
    if data.bitrate is not None:
        coordinator.rcp_bitrate_cache[cam_id] = data.bitrate
    if data.alarm_catalog is not None:
        coordinator.rcp_alarm_catalog_cache[cam_id] = data.alarm_catalog
    if data.motion_zones is not None:
        coordinator.rcp_motion_zones_cache[cam_id] = data.motion_zones
    if data.motion_coords is not None:
        coordinator.rcp_motion_coords_cache[cam_id] = data.motion_coords
    if data.tls_cert is not None:
        coordinator.rcp_tls_cert_cache[cam_id] = data.tls_cert
    if data.network_services is not None:
        coordinator.rcp_network_services_cache[cam_id] = data.network_services
    if data.iva_catalog is not None:
        coordinator.rcp_iva_catalog_cache[cam_id] = data.iva_catalog
