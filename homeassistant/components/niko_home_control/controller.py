"""The niko_home_control controller."""
from nikohomecontrol import NikoHomeControl


class NikoHomeControlController:
    """The niko home control controller."""

    def __init__(self, host, port) -> None:
        """Init niko home control controller."""
        self._controller = NikoHomeControl({"ip": host, "port": port})

    def system_info(self):
        """Get system info."""
        return self._controller.system_info()

    def list_actions(self):
        """List actions."""
        return self._controller.list_actions_raw()

    def list_energy(self):
        """List energy."""
        return self._controller.list_energy()

    def list_locations(self):
        """List locations."""
        return self._controller.list_locations_raw()

    def list_thermostats(self):
        """List thermostats."""
        return self._controller.list_thermostats_raw()

    def execute_actions(self, action_id, value):
        """Execute actions."""
        return self._controller.execute_actions(action_id, value)
