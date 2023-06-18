"""API for Hydrawise."""

import time

from .hydrawiser_api import customer_details, set_zones, status_schedule


class HydraWiseRelay:
    """HydraWise Relay."""

    controller_id: int
    relay_id: int  # Unique ID of relay
    relay: int  # Physical number of zone
    name: str
    timestr: str  # Next time zone will water
    time: int  # Number of seconds until next programmed run. 1 if running
    run: str  # Length of next run, if in progress indicates remaining time in seconds

    def __init__(self, controller_id, relay_info) -> None:
        """Initialize relay."""
        self.controller_id = controller_id
        self.relay_id = relay_info["relay_id"]
        self.relay = relay_info["relay"]
        self.name = relay_info["name"]
        self.timestr = relay_info["timestr"]
        self.time = relay_info["time"]
        self.run = relay_info["run"]

    def is_zone_running(self) -> bool:
        """State of the specified zone.

        :param zone: The zone to check.
        :type zone: int
        :returns: Returns True if the zone is currently running, otherwise
                  returns False if the zone is not running.
        :rtype: boolean
        """

        return self.time == 1

    def time_remaining(self):
        """Amount of watering time left in seconds.

        :param zone: The zone to check.
        :type zone: int
        :returns: If the zone is not running returns 0. If the zone doesn't
                  exist returns None. Otherwise returns number of seconds left
                  in the watering cycle.
        :rtype: None or seconds left in the waterting cycle.
        """
        if self.is_zone_running():
            return self.run

        return 0


class HydraWiseController:
    """HydraWise Controller."""

    name: str
    controller_id: int
    relays: list[HydraWiseRelay]
    master_relay: int
    master_time: int

    def __init__(self, controller_details, status_details) -> None:
        """Initialize controller."""
        self.name = controller_details["name"]
        self.controller_id = controller_details["controller_id"]
        self.master_relay = status_details["master"]
        self.master_timer = status_details["master_timer"]
        self.relays = []
        for relay in status_details["relays"]:
            self.relays.append(HydraWiseRelay(self.controller_id, relay))


class Hydrawiser:
    """Hydrawiser."""

    controllers: list[HydraWiseController]

    def __init__(self, user_token) -> None:
        """Construct."""

        self._user_token = user_token
        self.controllers = []
        self.update_controllers()

    def update_controllers(self) -> bool:
        """Pull controller information.

        :returns: True if successful, otherwise False.
        :rtype: boolean
        """

        # Read the controller information.
        controller_info = customer_details(self._user_token)

        if controller_info is None:
            return False

        controllers = []
        for controller in controller_info["controllers"]:
            controller_status = status_schedule(
                self._user_token, controller["controller_id"]
            )
            controllers.append(HydraWiseController(controller, controller_status))

        self.controllers = controllers
        return True

    def get_controller(self, controller_id) -> HydraWiseController | None:
        """Get controller."""
        for controller in self.controllers:
            if controller.controller_id == controller_id:
                return controller

        return None

    def get_relay(self, controller_id, relay_id) -> HydraWiseRelay | None:
        """Get relay."""
        controller = self.get_controller(controller_id)
        if controller is None:
            return None

        for relay in controller.relays:
            if relay.relay_id == relay_id:
                return relay

        return None

    def convert_days_to_cmd(self, days):
        """Add days to current time."""
        if days <= 0:
            return 0

        # 1 day = 60 * 60 * 24 seconds = 86400
        return time.mktime(time.localtime()) + (days * 86400)

    def suspend_all(self, controller_id, days):
        """Suspend all zones."""
        zone_cmd = "suspendall"
        relay_id = None
        time_cmd = self.convert_days_to_cmd(days)

        return set_zones(self._user_token, controller_id, zone_cmd, relay_id, time_cmd)

    def suspend_zone(self, days, relay: HydraWiseRelay):
        """Suspend zone for an amount of time.

        :param days: Number of days to suspend the zone(s)
        :param relay: The zone to suspend.
        :returns: The response from set_zones() or None if there was an error.
        :rtype: None or string
        """
        zone_cmd = "suspend"
        time_cmd = self.convert_days_to_cmd(days)

        return set_zones(
            self._user_token, relay.controller_id, zone_cmd, relay.relay_id, time_cmd
        )

    def run_all(self, controller_id, minutes):
        """Run all zones."""
        zone_cmd = "runall"
        relay_id = None
        time_cmd = minutes * 60

        return set_zones(self._user_token, controller_id, zone_cmd, relay_id, time_cmd)

    def run_zone(self, minutes, relay: HydraWiseRelay):
        """Run zone for an amount of time.

        :param minutes: The number of minutes to run.
        :param relay: The zone number to run.
        :returns: The response from set_zones() or None if there was an error.
        :rtype: None or string
        """
        zone_cmd = "run"
        time_cmd = minutes * 60

        return set_zones(
            self._user_token, relay.controller_id, zone_cmd, relay.relay_id, time_cmd
        )

    def stop_all(self, controller_id):
        """Stop all zones."""
        zone_cmd = "stopall"
        relay_id = None
        time_cmd = 0

        return set_zones(self._user_token, controller_id, zone_cmd, relay_id, time_cmd)

    def stop_zone(self, relay: HydraWiseRelay):
        """Stop zone."""
        zone_cmd = "stop"
        time_cmd = 0

        return set_zones(
            self._user_token, relay.controller_id, zone_cmd, relay.relay_id, time_cmd
        )
