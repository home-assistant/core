"""HA service registrations (trigger_snapshot, rules, motion zones, privacy masks, camera sharing, event migration/deletion, …).

Extracted from __init__.py's _register_services — a single ~1300-line function
holding ~20 independent, low-coupling service handlers purely for registration.
Each handler only closes over `hass` (no coordinator/self capture) and looks up
the active config entry's coordinator per-call via
`hass.config_entries.async_loaded_entries(DOMAIN)`, so this was a mechanical
move with no behavior change.
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
import re
import shutil
import time
from typing import NoReturn

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _raise_http_error(action: str, status: int) -> NoReturn:
    """Raise a translated HomeAssistantError for a non-2xx cloud response."""
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="http_error",
        translation_placeholders={"action": action, "status": str(status)},
    )


def _raise_http_error_with_body(action: str, status: int, body: str) -> NoReturn:
    """Raise a translated HomeAssistantError including the response body."""
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="http_error_with_body",
        translation_placeholders={
            "action": action,
            "status": str(status),
            "body": body[:200],
        },
    )


def _raise_privacy_blocked(action: str) -> NoReturn:
    """Raise a translated HomeAssistantError for a privacy-mode-blocked write."""
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="privacy_blocked",
        translation_placeholders={"action": action},
    )


def _raise_index_out_of_range(index: int, count: int) -> NoReturn:
    """Raise a translated ServiceValidationError for an out-of-range zone index."""
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="index_out_of_range",
        translation_placeholders={"index": str(index), "count": str(count)},
    )


def _register_services(hass: HomeAssistant) -> None:  # noqa: C901 -- ~20 independent, low-coupling service-handler closures registered in one place (see module docstring); splitting the registration would scatter one coherent handler-registry
    """Register HA services (skip if already registered)."""

    async def handle_trigger_snapshot(call: ServiceCall) -> None:
        """Force an immediate refresh.

        Without `entity_id`: refresh all cameras (data + images). With an
        `entity_id`: refresh only that camera's image — and skip the full
        coordinator tick. The Lovelace card passes its own camera on mount /
        tab-switch / its 60 s timer, so a dashboard with N cameras would
        otherwise fire N×(all cameras) image refreshes (and N coordinator ticks)
        and hammer Bosch's ~3-concurrent-session budget. The periodic coordinator
        poll keeps event/state data fresh independently.
        """
        target = call.data.get("entity_id")
        # entity_id may arrive as a list (HA target selector) or a bare string.
        if isinstance(target, list):
            target = target[0] if target else None
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if not coord:
                continue
            if target:
                for cam in coord.camera_entities.values():
                    if getattr(cam, "entity_id", None) == target:
                        hass.async_create_task(cam.async_trigger_image_refresh(delay=0))
                continue
            # Fire coordinator refresh in background — do NOT await it.
            # async_request_refresh() awaits the full coordinator tick which can
            # take 6-22 s; blocking here freezes the card until the tick finishes.
            hass.async_create_task(coord.async_request_refresh())
            for cam in coord.camera_entities.values():
                hass.async_create_task(cam.async_trigger_image_refresh(delay=0))

    async def handle_open_live_connection(call: ServiceCall) -> None:
        """Try to open a live proxy connection for a specific camera."""
        cam_id = call.data.get("camera_id", "")
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        is_renewal = bool(call.data.get("renewal", False))
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                result = await coord.try_live_connection(cam_id, is_renewal=is_renewal)
                if result:
                    # avoids circular import (see live_connection.py:
                    # __init__.py defines _redact_creds after importing
                    # this module's services)
                    from . import _redact_creds  # noqa: PLC0415

                    _LOGGER.info(
                        "Live connection established: %s", _redact_creds(result)
                    )
                    return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="live_connection_failed",
            translation_placeholders={"cam_id_prefix": cam_id[:8]},
        )

    async def handle_create_rule(call: ServiceCall) -> None:
        """Create a cloud-side schedule rule for a camera."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        name = call.data.get("name", "HA Rule")
        start_time = call.data.get("start_time", "00:00:00")
        end_time = call.data.get("end_time", "23:59:00")
        weekdays = call.data.get("weekdays", [0, 1, 2, 3, 4, 5, 6])
        is_active = call.data.get("is_active", True)
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                payload = {
                    "id": None,
                    "name": name,
                    "isActive": is_active,
                    "startTime": start_time,
                    "endTime": end_time,
                    "weekdays": weekdays,
                }
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.post(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/rules",
                            headers=headers,
                            json=payload,
                        ) as resp:
                            if resp.status in (200, 201):
                                result = await resp.json()
                                _LOGGER.info("Rule created: %s", result)
                            else:
                                _raise_http_error("Create rule", resp.status)
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Create rule",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_delete_rule(call: ServiceCall) -> None:
        """Delete a cloud-side schedule rule."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        rule_id = call.data.get("rule_id", "")
        if not cam_id or not rule_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id and rule_id"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {"Authorization": f"Bearer {coord.token}"}
                try:
                    async with asyncio.timeout(10):
                        async with session.delete(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/rules/{rule_id}",
                            headers=headers,
                        ) as resp:
                            if resp.status == 204:
                                _LOGGER.info("Rule %s deleted", rule_id)
                            else:
                                _raise_http_error("Delete rule", resp.status)
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Delete rule",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_update_rule(call: ServiceCall) -> None:
        """Update a cloud-side schedule rule (activate/deactivate, change times)."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        rule_id = call.data.get("rule_id", "")
        if not cam_id or not rule_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id and rule_id"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                # Fetch current rule from cache or API (API needs all fields for PUT)
                existing = None
                for rule in coord.rules_cache.get(cam_id, []):
                    if rule.get("id") == rule_id:
                        existing = dict(rule)
                        break
                if not existing:
                    # Fetch from API if not in cache
                    try:
                        async with asyncio.timeout(10):
                            async with session.get(
                                f"{CLOUD_API}/v11/video_inputs/{cam_id}/rules",
                                headers=headers,
                            ) as resp:
                                if resp.status == 200:
                                    rules = await resp.json()
                                    for rule in rules:
                                        if rule.get("id") == rule_id:
                                            existing = dict(rule)
                                            break
                    except Exception as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="unexpected_error",
                            translation_placeholders={
                                "action": "Fetch rules for update",
                                "error": str(err),
                            },
                        ) from err
                if not existing:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="not_found",
                        translation_placeholders={"kind": "Rule", "id": rule_id},
                    )
                # Overlay provided fields
                if "name" in call.data:
                    existing["name"] = call.data["name"]
                if "is_active" in call.data:
                    existing["isActive"] = call.data["is_active"]
                if "start_time" in call.data:
                    existing["startTime"] = call.data["start_time"]
                if "end_time" in call.data:
                    existing["endTime"] = call.data["end_time"]
                if "weekdays" in call.data:
                    existing["weekdays"] = call.data["weekdays"]
                try:
                    async with asyncio.timeout(10):
                        async with session.put(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/rules/{rule_id}",
                            headers=headers,
                            json=existing,
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                _LOGGER.info("Rule %s updated", rule_id)
                                await coord.async_request_refresh()
                            else:
                                body = await resp.text()
                                _raise_http_error_with_body(
                                    "Update rule", resp.status, body
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Update rule",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_set_motion_zones(call: ServiceCall) -> None:
        """Set motion detection zones for a camera (normalized coordinates 0.0–1.0)."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        zones = call.data.get("zones", [])
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        if not isinstance(zones, list):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_must_be_list",
                translation_placeholders={"argument": "zones"},
            )
        # Validate zone coordinates
        for i, z in enumerate(zones):
            for key in ("x", "y", "w", "h"):
                if key not in z:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="missing_field",
                        translation_placeholders={
                            "kind": "zone",
                            "index": str(i),
                            "field": key,
                        },
                    )
                try:
                    val = float(z[key])
                except (TypeError, ValueError) as err:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="value_out_of_range",
                        translation_placeholders={
                            "kind": "zone",
                            "index": str(i),
                            "field": key,
                            "value": str(z[key]),
                        },
                    ) from err
                if val < 0.0 or val > 1.0:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="value_out_of_range",
                        translation_placeholders={
                            "kind": "zone",
                            "index": str(i),
                            "field": key,
                            "value": f"{val:.3f}",
                        },
                    )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.post(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/motion_sensitive_areas",
                            headers=headers,
                            json=zones,
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                _LOGGER.info(
                                    "Motion zones set for %s (%d zones)",
                                    cam_id[:8],
                                    len(zones),
                                )
                                await coord.async_request_refresh()
                            elif resp.status == 443:
                                _raise_privacy_blocked("Set motion zones")
                            else:
                                body = await resp.text()
                                _raise_http_error_with_body(
                                    "Set motion zones", resp.status, body
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Set motion zones",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_get_motion_zones(call: ServiceCall) -> None:
        """Read current motion detection zones and show as persistent notification."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {"Authorization": f"Bearer {coord.token}"}
                try:
                    async with asyncio.timeout(10):
                        async with session.get(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/motion_sensitive_areas",
                            headers=headers,
                        ) as resp:
                            if resp.status == 200:
                                zones = await resp.json()
                                if not zones:
                                    msg = "Keine Motion-Zonen konfiguriert."
                                else:
                                    lines = [f"{len(zones)} Motion-Zone(n):"]
                                    for i, z in enumerate(zones):
                                        lines.append(
                                            f"• Zone {i + 1}: x={z.get('x', 0):.3f} y={z.get('y', 0):.3f} w={z.get('w', 0):.3f} h={z.get('h', 0):.3f}"
                                        )
                                    msg = "\n".join(lines)
                                _LOGGER.info("Motion zones for %s: %s", cam_id[:8], msg)
                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": "Motion-Zonen",
                                        "message": msg,
                                        "notification_id": "bosch_motion_zones",
                                    },
                                )
                            elif resp.status == 443:
                                msg = "Motion-Zonen nicht verfügbar (HTTP 443). Mögliche Ursache: Privacy-Mode ist aktiv."
                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": "Motion-Zonen",
                                        "message": msg,
                                        "notification_id": "bosch_motion_zones",
                                    },
                                )
                                _raise_privacy_blocked("get_motion_zones")
                            else:
                                body = await resp.text()
                                _raise_http_error_with_body(
                                    "Get motion zones", resp.status, body
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Get motion zones",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_share_camera(call: ServiceCall) -> None:
        """Share one or more cameras with a friend (time-limited)."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        friend_id = call.data.get("friend_id", "")
        camera_ids = call.data.get("camera_ids", [])
        days = call.data.get("days", 30)
        if not friend_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "friend_id"},
            )
        if not camera_ids:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_ids"},
            )
        if isinstance(camera_ids, str):
            camera_ids = [camera_ids]
        now = datetime.now(UTC)
        end = now + timedelta(days=int(days))
        shares = [
            {
                "videoInputId": cid,
                "shareTime": {
                    "start": now.isoformat(),
                    "end": end.isoformat(),
                },
            }
            for cid in camera_ids
        ]
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.put(
                            f"{CLOUD_API}/v11/friends/{friend_id}/share",
                            headers=headers,
                            json=shares,
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                _LOGGER.info(
                                    "Shared %d camera(s) with friend %s for %d days",
                                    len(camera_ids),
                                    friend_id[:8],
                                    days,
                                )
                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": "Kamera-Freigabe",
                                        "message": f"{len(camera_ids)} Kamera(s) für {days} Tage geteilt.",
                                    },
                                )
                            else:
                                body = await resp.text()
                                _raise_http_error_with_body(
                                    "Share camera", resp.status, body
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Share camera",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_get_privacy_masks(call: ServiceCall) -> None:
        """Read current privacy masks and show as persistent notification."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {"Authorization": f"Bearer {coord.token}"}
                try:
                    async with asyncio.timeout(10):
                        async with session.get(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/privacy_masks",
                            headers=headers,
                        ) as resp:
                            if resp.status == 200:
                                masks = await resp.json()
                                if not masks:
                                    msg = "Keine Privacy-Masken konfiguriert."
                                else:
                                    lines = [f"{len(masks)} Privacy-Maske(n):"]
                                    for i, m in enumerate(masks):
                                        lines.append(
                                            f"• Maske {i + 1}: x={m.get('x', 0):.3f} y={m.get('y', 0):.3f} w={m.get('w', 0):.3f} h={m.get('h', 0):.3f}"
                                        )
                                    msg = "\n".join(lines)
                                _LOGGER.info(
                                    "Privacy masks for %s: %s", cam_id[:8], msg
                                )
                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": "Privacy-Masken",
                                        "message": msg,
                                        "notification_id": "bosch_privacy_masks",
                                    },
                                )
                            elif resp.status == 443:
                                msg = "Privacy-Masken nicht verfügbar (HTTP 443). Mögliche Ursache: Privacy-Mode ist aktiv."
                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": "Privacy-Masken",
                                        "message": msg,
                                        "notification_id": "bosch_privacy_masks",
                                    },
                                )
                                _raise_privacy_blocked("get_privacy_masks")
                            else:
                                body = await resp.text()
                                _raise_http_error_with_body(
                                    "Get privacy masks", resp.status, body
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Get privacy masks",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_set_privacy_masks(call: ServiceCall) -> None:
        """Set privacy mask zones for a camera (normalized coordinates 0.0–1.0)."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        masks = call.data.get("masks", [])
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        if not isinstance(masks, list):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_must_be_list",
                translation_placeholders={"argument": "masks"},
            )
        for i, m in enumerate(masks):
            for key in ("x", "y", "w", "h"):
                if key not in m:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="missing_field",
                        translation_placeholders={
                            "kind": "mask",
                            "index": str(i),
                            "field": key,
                        },
                    )
                try:
                    val = float(m[key])
                except (TypeError, ValueError) as err:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="value_out_of_range",
                        translation_placeholders={
                            "kind": "mask",
                            "index": str(i),
                            "field": key,
                            "value": str(m[key]),
                        },
                    ) from err
                if val < 0.0 or val > 1.0:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="value_out_of_range",
                        translation_placeholders={
                            "kind": "mask",
                            "index": str(i),
                            "field": key,
                            "value": f"{val:.3f}",
                        },
                    )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.post(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/privacy_masks",
                            headers=headers,
                            json=masks,
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                _LOGGER.info(
                                    "Privacy masks set for %s (%d masks)",
                                    cam_id[:8],
                                    len(masks),
                                )
                                await coord.async_request_refresh()
                            elif resp.status == 443:
                                _raise_privacy_blocked("Set privacy masks")
                            else:
                                body = await resp.text()
                                _raise_http_error_with_body(
                                    "Set privacy masks", resp.status, body
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Set privacy masks",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_delete_motion_zone(call: ServiceCall) -> None:
        """Delete a single motion detection zone by index."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        zone_index = call.data.get("zone_index", -1)
        if not cam_id or zone_index < 0:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id and zone_index"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                # Fetch current zones, remove the one at index, re-POST
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.get(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/motion_sensitive_areas",
                            headers=headers,
                        ) as resp:
                            if resp.status != 200:
                                _raise_http_error(
                                    "delete_motion_zone fetch", resp.status
                                )
                            zones = await resp.json()
                    if zone_index >= len(zones):
                        _raise_index_out_of_range(zone_index, len(zones))
                    removed = zones.pop(zone_index)
                    _LOGGER.info("Removing zone %d: %s", zone_index, removed)
                    async with asyncio.timeout(10):
                        async with session.post(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/motion_sensitive_areas",
                            headers=headers,
                            json=zones,
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                _LOGGER.info(
                                    "Zone %d deleted, %d zones remaining",
                                    zone_index,
                                    len(zones),
                                )
                                await coord.async_request_refresh()
                            else:
                                _raise_http_error(
                                    "delete_motion_zone POST", resp.status
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "delete_motion_zone",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_get_lighting_schedule(call: ServiceCall) -> None:
        """Read the full lighting schedule and show as persistent notification."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                try:
                    cached = getattr(coord, "lighting_options_cache", {}).get(cam_id)
                    if cached:
                        data = cached
                    else:
                        session = await async_get_bosch_cloud_session(hass)
                        headers = {"Authorization": f"Bearer {coord.token}"}
                        async with asyncio.timeout(10):
                            async with session.get(
                                f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting_options",
                                headers=headers,
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                else:
                                    _raise_http_error(
                                        "get_lighting_schedule", resp.status
                                    )
                    sched = data.get("scheduleStatus", "?")
                    on_time = data.get("generalLightOnTime", "?")
                    off_time = data.get("generalLightOffTime", "?")
                    threshold = data.get("darknessThreshold", "?")
                    motion = data.get("lightOnMotion", False)
                    followup = data.get("lightOnMotionFollowUpTimeSeconds", 0)
                    front = data.get("frontIlluminatorInGeneralLightOn", False)
                    wall = data.get("wallwasherInGeneralLightOn", False)
                    intensity = data.get("frontIlluminatorGeneralLightIntensity", 1.0)
                    msg = (
                        f"Modus: {sched}\n"
                        f"Zeitplan: {on_time} → {off_time}\n"
                        f"Dunkelheits-Schwelle: {threshold}\n"
                        f"Licht bei Bewegung: {'Ja' if motion else 'Nein'} ({followup}s Nachlauf)\n"
                        f"Frontlicht: {'An' if front else 'Aus'} (Intensität: {intensity})\n"
                        f"Wallwasher: {'An' if wall else 'Aus'}"
                    )
                    _LOGGER.info("Lighting schedule for %s: %s", cam_id[:8], msg)
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "Licht-Zeitplan",
                            "message": msg,
                            "notification_id": "bosch_lighting",
                        },
                    )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "get_lighting_schedule",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_set_lighting_schedule(call: ServiceCall) -> None:
        """Set the LED lighting schedule (on/off time, motion trigger, darkness threshold).

        Outdoor cameras with LED light only (mirrors the Python CLI's
        GET-merge-PUT to /v11/video_inputs/{id}/lighting_options — Bosch's
        cloud API supports write here already, no local RCP dependency).
        """
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        if not cam_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id"},
            )
        on_time = call.data.get("on_time")
        off_time = call.data.get("off_time")
        motion = call.data.get("motion")
        threshold = call.data.get("threshold")
        if threshold is not None:
            try:
                threshold = float(threshold)
            except (TypeError, ValueError) as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="value_out_of_range",
                    translation_placeholders={
                        "kind": "lighting_schedule",
                        "index": "0",
                        "field": "threshold",
                        "value": str(threshold),
                    },
                ) from err
            if not 0.0 <= threshold <= 1.0:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="value_out_of_range",
                    translation_placeholders={
                        "kind": "lighting_schedule",
                        "index": "0",
                        "field": "threshold",
                        "value": f"{threshold:.3f}",
                    },
                )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.get(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting_options",
                            headers=headers,
                        ) as get_resp:
                            if get_resp.status != 200:
                                body = await get_resp.text()
                                _raise_http_error_with_body(
                                    "Set lighting schedule (fetch current)",
                                    get_resp.status,
                                    body,
                                )
                            data = await get_resp.json()
                    if on_time:
                        data["generalLightOnTime"] = (
                            on_time if len(on_time.split(":")) == 3 else f"{on_time}:00"
                        )
                    if off_time:
                        data["generalLightOffTime"] = (
                            off_time
                            if len(off_time.split(":")) == 3
                            else f"{off_time}:00"
                        )
                    if motion is not None:
                        data["lightOnMotion"] = bool(motion)
                    if threshold is not None:
                        data["darknessThreshold"] = threshold
                    data["scheduleStatus"] = "FOLLOW_SCHEDULE"
                    async with asyncio.timeout(10):
                        async with session.put(
                            f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting_options",
                            headers=headers,
                            json=data,
                        ) as put_resp:
                            if put_resp.status in (200, 204):
                                _LOGGER.info(
                                    "Lighting schedule set for %s: %s → %s",
                                    cam_id[:8],
                                    data.get("generalLightOnTime"),
                                    data.get("generalLightOffTime"),
                                )
                                # Optimistic cache update + write-lock, same
                                # pattern as _privacy_sound_cache/_ledlights_cache
                                # (slow_tier.py) — without this, a slow-tier poll
                                # landing before the next rotation completes can
                                # serve get_lighting_schedule stale pre-write data
                                # for up to a full poll interval (bug-hunt finding,
                                # 3-agent verification 2026-07-11).
                                coord.lighting_options_cache[cam_id] = data
                                coord.lighting_options_set_at[cam_id] = time.monotonic()
                                await coord.async_request_refresh()
                            else:
                                body = await put_resp.text()
                                _raise_http_error_with_body(
                                    "Set lighting schedule", put_resp.status, body
                                )
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Set lighting schedule",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_rename_camera(call: ServiceCall) -> None:
        """Rename a camera via the Bosch cloud API."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        cam_id = call.data.get("camera_id", "")
        new_name = call.data.get("new_name", "")
        if not cam_id or not new_name:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "camera_id and new_name"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.put(
                            f"{CLOUD_API}/v11/video_inputs",
                            headers=headers,
                            json={
                                "videoInputId": cam_id,
                                "title": new_name,
                                "timeZone": hass.config.time_zone,
                            },
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                _LOGGER.info(
                                    "Camera %s renamed to '%s'", cam_id[:8], new_name
                                )
                                await coord.async_request_refresh()
                            else:
                                _raise_http_error("Rename", resp.status)
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Rename",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_invite_friend(call: ServiceCall) -> None:
        """Invite a friend for camera sharing."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        email = call.data.get("email", "")
        if not email:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "email"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {
                    "Authorization": f"Bearer {coord.token}",
                    "Content-Type": "application/json",
                }
                try:
                    async with asyncio.timeout(10):
                        async with session.post(
                            f"{CLOUD_API}/v11/friends",
                            headers=headers,
                            json={"invitationEmail": email, "nickName": email},
                        ) as resp:
                            if resp.status in (200, 201):
                                data = await resp.json()
                                email_domain = (
                                    email.split("@")[-1]
                                    if "@" in email
                                    else "[no-domain]"
                                )
                                _LOGGER.info(
                                    "Friend invited: *@%s (ID: %s)",
                                    email_domain,
                                    data.get("id", "?"),
                                )
                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": "Kamera-Freigabe",
                                        "message": f"Einladung an {email} gesendet. Friend-ID: {data.get('id', '?')}",
                                    },
                                )
                            else:
                                body = await resp.text()
                                _raise_http_error_with_body("Invite", resp.status, body)
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Invite",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_list_friends(call: ServiceCall) -> None:
        """List all friends and camera shares."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {"Authorization": f"Bearer {coord.token}"}
                try:
                    async with asyncio.timeout(10):
                        async with session.get(
                            f"{CLOUD_API}/v11/friends", headers=headers
                        ) as resp:
                            if resp.status == 200:
                                friends = await resp.json()
                                if not friends:
                                    msg = "Keine Freunde / Kamera-Freigaben."
                                else:
                                    lines = [f"{len(friends)} Freund(e):"]
                                    for f in friends:
                                        email = f.get(
                                            "email", f.get("invitationEmail", "?")
                                        )
                                        status = f.get(
                                            "status", f.get("invitationStatus", "?")
                                        )
                                        fid = f.get("id", "?")
                                        shares = f.get("sharedVideoInputs", [])
                                        lines.append(
                                            f"• {email} (Status: {status}, ID: {fid}, Kameras: {len(shares)})"
                                        )
                                    msg = "\n".join(lines)
                                _LOGGER.info("Friends: %s", msg)
                                await hass.services.async_call(
                                    "persistent_notification",
                                    "create",
                                    {
                                        "title": "Kamera-Freigaben",
                                        "message": msg,
                                        "notification_id": "bosch_friends_list",
                                    },
                                )
                            else:
                                _raise_http_error("List friends", resp.status)
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "List friends",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_remove_friend(call: ServiceCall) -> None:
        """Remove a friend and revoke camera shares."""
        # Local import (not top-level): keeps unittest.mock.patch(
        # "custom_components.bosch_shc_camera.async_get_bosch_cloud_session"/
        # ".CLOUD_API") working the same way it did before this handler moved
        # out of __init__.py — those patches target the package's own
        # namespace, not services.py's.
        from . import (  # noqa: PLC0415
            CLOUD_API as CLOUD_API,
            async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        )

        friend_id = call.data.get("friend_id", "")
        if not friend_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "friend_id"},
            )
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if coord:
                session = await async_get_bosch_cloud_session(hass)
                headers = {"Authorization": f"Bearer {coord.token}"}
                try:
                    async with asyncio.timeout(10):
                        async with session.delete(
                            f"{CLOUD_API}/v11/friends/{friend_id}", headers=headers
                        ) as resp:
                            if resp.status in (200, 201, 204):
                                _LOGGER.info("Friend %s removed", friend_id)
                            else:
                                _raise_http_error("Remove friend", resp.status)
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="unexpected_error",
                        translation_placeholders={
                            "action": "Remove friend",
                            "error": str(err),
                        },
                    ) from err
                break

    async def handle_migrate_flat_events(call: ServiceCall) -> None:
        """Move flat event files (camera/file) into date hierarchy (camera/year/month/day/file)."""
        _pat = re.compile(
            r"^(?:(?P<camera>.+?)_)?(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{2}-\d{2}-\d{2})_"
            r"(?P<etype>[A-Z_]+)_[0-9A-F]+\.(?P<ext>jpg|jpeg|mp4)$",
            re.IGNORECASE,
        )
        total = 0
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if not coord:
                continue
            opts = coord.options
            base_str = (opts.get("download_path") or "").strip()
            if not base_str:
                continue
            base = Path(base_str)
            if not base.is_dir():
                continue

            def _migrate(base: Path) -> int:
                moved = 0
                for cam_dir in base.iterdir():
                    if not cam_dir.is_dir():
                        continue
                    for f in list(cam_dir.iterdir()):
                        if not f.is_file():
                            continue
                        m = _pat.match(f.name)
                        if not m:
                            continue
                        y, mo, d = m.group("date").split("-")
                        dest_dir = cam_dir / y / mo / d
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest = dest_dir / f.name
                        if dest.exists():
                            _LOGGER.warning(
                                "migrate_flat_events: skip %s — dest exists", f.name
                            )
                            continue
                        shutil.move(str(f), str(dest))
                        moved += 1
                return moved

            n = await hass.async_add_executor_job(_migrate, base)
            total += n
            _LOGGER.info("migrate_flat_events: moved %d file(s) in %s", n, base)

        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Bosch Kamera",
                "message": f"Flat-file migration complete: {total} file(s) moved to date hierarchy.",
                "notification_id": "bosch_migrate",
            },
        )

    async def handle_delete_event(call: ServiceCall) -> None:
        """Delete a local event file by file path or by camera + date."""
        file_path = (call.data.get("file_path") or "").strip()
        camera = (call.data.get("camera") or "").strip()
        date = (call.data.get("date") or "").strip()

        if not file_path and not camera:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="argument_required",
                translation_placeholders={"argument": "file_path or camera"},
            )

        deleted = 0
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord = entry.runtime_data
            if not coord:
                continue
            opts = coord.options
            base_str = (opts.get("download_path") or "").strip()
            if not base_str:
                continue
            base = Path(base_str).resolve()

            def _delete(base: Path, file_path: str, camera: str, date: str) -> int:
                _pat2 = re.compile(
                    r"^(?:(?P<cam>.+?)_)?(?P<date>\d{4}-\d{2}-\d{2})_",
                    re.IGNORECASE,
                )
                count = 0
                if file_path:
                    target = Path(file_path).resolve()
                    try:
                        target.relative_to(base)
                    except ValueError:
                        _LOGGER.warning(
                            "delete_event: path %s outside base %s — rejected",
                            target,
                            base,
                        )
                        return 0
                    if target.is_file():
                        target.unlink()
                        count += 1
                    return count
                # camera + optional date filter. Unreachable defensively: the
                # service raises argument_required when file_path AND camera are
                # both empty, so with file_path empty here camera is always set.
                if not camera:  # pragma: no cover
                    return 0
                cam_dir = (base / camera).resolve()
                try:
                    cam_dir.relative_to(base)
                except ValueError:
                    return 0
                if not cam_dir.is_dir():
                    return 0
                for f in cam_dir.rglob("*"):
                    if not f.is_file():
                        continue
                    m = _pat2.match(f.name)
                    if not m:
                        continue
                    if date and m.group("date") != date:
                        continue
                    f.unlink()
                    count += 1
                # clean up empty dirs
                for d in sorted(cam_dir.rglob("*"), reverse=True):
                    if d.is_dir():
                        with contextlib.suppress(OSError):
                            d.rmdir()
                return count

            n = await hass.async_add_executor_job(
                _delete, base, file_path, camera, date
            )
            deleted += n
            break

        _LOGGER.info("delete_event: deleted %d file(s)", deleted)
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Bosch Kamera",
                "message": f"Deleted {deleted} event file(s).",
                "notification_id": "bosch_delete_event",
            },
        )

    if not hass.services.has_service(DOMAIN, "trigger_snapshot"):
        hass.services.async_register(
            DOMAIN, "trigger_snapshot", handle_trigger_snapshot
        )
    if not hass.services.has_service(DOMAIN, "open_live_connection"):
        hass.services.async_register(
            DOMAIN, "open_live_connection", handle_open_live_connection
        )
    if not hass.services.has_service(DOMAIN, "create_rule"):
        hass.services.async_register(DOMAIN, "create_rule", handle_create_rule)
    if not hass.services.has_service(DOMAIN, "delete_rule"):
        hass.services.async_register(DOMAIN, "delete_rule", handle_delete_rule)
    if not hass.services.has_service(DOMAIN, "delete_motion_zone"):
        hass.services.async_register(
            DOMAIN, "delete_motion_zone", handle_delete_motion_zone
        )
    if not hass.services.has_service(DOMAIN, "get_lighting_schedule"):
        hass.services.async_register(
            DOMAIN, "get_lighting_schedule", handle_get_lighting_schedule
        )
    if not hass.services.has_service(DOMAIN, "set_lighting_schedule"):
        hass.services.async_register(
            DOMAIN, "set_lighting_schedule", handle_set_lighting_schedule
        )
    if not hass.services.has_service(DOMAIN, "get_privacy_masks"):
        hass.services.async_register(
            DOMAIN, "get_privacy_masks", handle_get_privacy_masks
        )
    if not hass.services.has_service(DOMAIN, "set_privacy_masks"):
        hass.services.async_register(
            DOMAIN, "set_privacy_masks", handle_set_privacy_masks
        )
    if not hass.services.has_service(DOMAIN, "update_rule"):
        hass.services.async_register(DOMAIN, "update_rule", handle_update_rule)
    if not hass.services.has_service(DOMAIN, "set_motion_zones"):
        hass.services.async_register(
            DOMAIN, "set_motion_zones", handle_set_motion_zones
        )
    if not hass.services.has_service(DOMAIN, "get_motion_zones"):
        hass.services.async_register(
            DOMAIN, "get_motion_zones", handle_get_motion_zones
        )
    if not hass.services.has_service(DOMAIN, "share_camera"):
        hass.services.async_register(DOMAIN, "share_camera", handle_share_camera)
    if not hass.services.has_service(DOMAIN, "rename_camera"):
        hass.services.async_register(DOMAIN, "rename_camera", handle_rename_camera)
    if not hass.services.has_service(DOMAIN, "invite_friend"):
        hass.services.async_register(DOMAIN, "invite_friend", handle_invite_friend)
    if not hass.services.has_service(DOMAIN, "list_friends"):
        hass.services.async_register(DOMAIN, "list_friends", handle_list_friends)
    if not hass.services.has_service(DOMAIN, "remove_friend"):
        hass.services.async_register(DOMAIN, "remove_friend", handle_remove_friend)
    if not hass.services.has_service(DOMAIN, "migrate_flat_events"):
        hass.services.async_register(
            DOMAIN, "migrate_flat_events", handle_migrate_flat_events
        )
    if not hass.services.has_service(DOMAIN, "delete_event"):
        hass.services.async_register(DOMAIN, "delete_event", handle_delete_event)
