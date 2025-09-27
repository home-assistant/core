"""The UptimeRobot integration."""

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
        if not coordinator.data:
            return

        new_monitors: list[UptimeRobotMonitor] = []
        for monitor in coordinator.data:
            if monitor.id not in known_devices:
                known_devices.add(monitor.id)
                new_monitors.append(monitor)

        if new_monitors:
            new_devices_callback(new_monitors)

    # Check for devices immediately
    _check_devices()

    return coordinator.async_add_listener(_check_devices)
