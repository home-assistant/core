"""Lock-specific helpers for the Matter integration.

Provides DoorLock cluster endpoint resolution and feature detection.
These are separated from the general Matter helpers (helpers.py) to
maintain single responsibility — general helpers handle node/device
resolution while this module handles lock-specific concerns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chip.clusters import Objects as clusters

from homeassistant.core import callback

if TYPE_CHECKING:
    from matter_server.client.models.node import MatterEndpoint, MatterNode

# DoorLock Feature bitmap from Matter SDK
DoorLockFeature = clusters.DoorLock.Bitmaps.Feature


@callback
def get_lock_endpoint_from_node(node: MatterNode) -> MatterEndpoint | None:
    """Get the DoorLock endpoint from a node.

    Returns the first endpoint that has the DoorLock cluster, or None if not found.
    """
    for endpoint in node.endpoints.values():
        if endpoint.has_cluster(clusters.DoorLock):
            return endpoint
    return None


def _get_feature_map(endpoint: MatterEndpoint) -> int | None:
    """Read the DoorLock FeatureMap attribute from an endpoint."""
    value: int | None = endpoint.get_attribute_value(
        None, clusters.DoorLock.Attributes.FeatureMap
    )
    return value


@callback
def lock_supports_usr_feature(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports USR (User) feature.

    The USR feature indicates the lock supports user and credential management
    commands like SetUser, GetUser, SetCredential, etc.
    """
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kUser)


@callback
def lock_supports_week_day_schedules(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports Week Day Schedules (WDSCH) feature."""
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kWeekDayAccessSchedules)


@callback
def lock_supports_year_day_schedules(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports Year Day Schedules (YDSCH) feature."""
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kYearDayAccessSchedules)


@callback
def lock_supports_holiday_schedules(endpoint: MatterEndpoint) -> bool:
    """Check if lock endpoint supports Holiday Schedules (HDSCH) feature."""
    feature_map = _get_feature_map(endpoint)
    if feature_map is None:
        return False
    return bool(feature_map & DoorLockFeature.kHolidaySchedules)
