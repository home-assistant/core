"""A Niko Action."""


class Action:
    """A Niko Action."""

    def __init__(self, action, hub):
        """Init Niko Action."""
        self.state = action["value1"]
        self._action_id = action["id"]
        self._type = action["type"]
        self._name = action["name"]
        self._hub = hub
        self._location = hub._locations[action["location"]]

    @property
    def location(self):
        """A Niko Action location."""
        return self._location

    @property
    def name(self):
        """A Niko Action state."""
        return self._name

    @property
    def action_id(self):
        """A Niko Action action_id."""
        return self._action_id

    @property
    def action_type(self):
        """The Niko Action type."""
        return self._type

    @property
    def is_on(self):
        """Is on."""
        return self.state != 0

    def turn_on(self, brightness=255):
        """Turn On."""
        return self._hub.execute_actions(self.action_id, brightness)

    def turn_off(self):
        """Turn off."""
        return self._hub.execute_actions(self.action_id, 0)

    def toggle(self):
        """Toggle on/off."""
        if self.is_on:
            return self.turn_off()

        return self.turn_on()

    def set_fan_speed(self, percentage):
        """Set percentage."""
        return self._hub.execute_actions(self.action_id, percentage)

    def is_light(self) -> bool:
        """Is a light."""
        return self.action_type == 1

    def is_dimmable(self) -> bool:
        """Is a dimmable light."""
        return self.action_type == 2

    def is_fan(self) -> bool:
        """Is a fan."""
        return self.action_type == 3

    def is_cover(self) -> bool:
        """Is a cover."""
        return self.action_type == 4
