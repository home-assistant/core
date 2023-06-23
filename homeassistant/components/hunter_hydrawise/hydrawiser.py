"""API for Hydrawise."""

from datetime import datetime, timedelta

from .pydrawise import Auth, Controller, Hydrawise, Zone


class Hydrawiser:
    """Hydrawiser."""

    hydrawise: Hydrawise
    controllers: list[Controller]
    zones: list[Zone]

    def __init__(self, username, password) -> None:
        """Construct."""

        self.hydrawise = Hydrawise(Auth(username, password))
        self.controllers = []
        self.zones = []

    async def async_update_controllers(self) -> bool:
        """Pull controller information.

        :returns: True if successful, otherwise False.
        :rtype: boolean
        """

        self.zones = []

        self.controllers = await self.hydrawise.get_controllers()
        for controller in self.controllers:
            zones = await self.hydrawise.get_zones(controller)
            for zone in zones:
                zone.controller_id = controller.id
                self.zones.append(zone)

        return True

    def get_controller(self, controller_id) -> Controller | None:
        """Get controller."""
        for controller in self.controllers:
            if controller.id == controller_id:
                return controller

        return None

    def get_zone(self, zone_id) -> Zone | None:
        """Get relay."""
        for zone in self.zones:
            if zone.id == zone_id:
                return zone

        return None

    async def async_suspend_all(self, controller_id, days):
        """Suspend all zones."""
        controller = self.get_controller(controller_id)
        if controller is None:
            raise TypeError

        until = datetime.now() + timedelta(days=days)
        await self.hydrawise.suspend_all_zones(controller, until)
        return await self.async_update_controllers()

    async def async_suspend_zone(self, zone_id, days):
        """Suspend zone."""
        zone = self.get_zone(zone_id)
        if zone is None:
            raise TypeError

        until = datetime.now() + timedelta(days=days)
        await self.hydrawise.suspend_zone(zone, until)
        return await self.async_update_controllers()

    async def async_resume_all(self, controller_id):
        """Resume all zones."""
        controller = self.get_controller(controller_id)
        if controller is None:
            raise TypeError

        await self.hydrawise.resume_all_zones(controller)
        return await self.async_update_controllers()

    async def async_resume_zone(self, zone_id):
        """Resume zone."""
        zone = self.get_zone(zone_id)
        if zone is None:
            raise TypeError

        await self.hydrawise.resume_zone(zone)
        return await self.async_update_controllers()

    async def async_run_all(self, controller_id, minutes=0):
        """Run all zones."""
        controller = self.get_controller(controller_id)
        if controller is None:
            raise TypeError

        duration = minutes * 60
        await self.hydrawise.start_all_zones(controller, custom_run_duration=duration)
        return await self.async_update_controllers()

    async def async_run_zone(self, zone_id, minutes=0):
        """Run zone."""
        zone = self.get_zone(zone_id)
        if zone is None:
            raise TypeError

        duration = minutes * 60
        await self.hydrawise.start_zone(
            zone, custom_run_duration=duration, stack_runs=True
        )
        return await self.async_update_controllers()

    async def async_stop_all(self, controller_id):
        """Stop all zones."""
        controller = self.get_controller(controller_id)
        if controller is None:
            raise TypeError

        await self.hydrawise.stop_all_zones(controller)
        return await self.async_update_controllers()

    async def async_stop_zone(self, zone_id):
        """Stop zone."""
        zone = self.get_zone(zone_id)
        if zone is None:
            raise TypeError

        await self.hydrawise.stop_zone(zone)
        return await self.async_update_controllers()
