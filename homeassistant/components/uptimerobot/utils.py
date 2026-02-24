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
    known_devices: set[str] = set()

    def _check_devices() -> None:
        """Check for new devices and call callback with any new monitors."""
        new_monitors: list[UptimeRobotMonitor] = []
        for monitor_id, monitor in coordinator.data.items():
            if monitor_id not in known_devices:
                known_devices.add(monitor_id)
                new_monitors.append(monitor)

        if new_monitors:
            new_devices_callback(new_monitors)

    # Check for devices immediately
    _check_devices()

    return coordinator.async_add_listener(_check_devices)
