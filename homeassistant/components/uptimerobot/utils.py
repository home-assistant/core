"""Utility functions for the UptimeRobot integration."""

from __future__ import annotations

from collections.abc import Callable

from pyuptimerobot import UptimeRobotMonitor

from .coordinator import UptimeRobotDataUpdateCoordinator


def new_device_listener(
    coordinator: UptimeRobotDataUpdateCoordinator,
    new_devices_callback: Callable[[list[UptimeRobotMonitor]], None],
) -> Callable[[], None]:
    """Subscribe to coordinator updates to check for new devices."""
    known_devices: set[int] = set()

    def _check_devices() -> None:
        """Check for new devices and call callback with any new monitors."""
        new_ids = coordinator.data.keys() - known_devices
        if new_ids:
            known_devices.update(new_ids)
            new_devices_callback([coordinator.data[i] for i in new_ids])

    # Check for devices immediately
    _check_devices()

    return coordinator.async_add_listener(_check_devices)
