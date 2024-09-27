"""A Niko Action."""


class Action:
    """A Niko Action."""

    def __init__(self, action, hub):
        """Init Niko Action."""
        self._action_id = action["id"]
        self._state = action["value1"]
        self._type = action["type"]
        self._name = action["name"]
        self._attr_is_on = action["value1"] != 0
        self._callbacks = set()
        self._hub = hub
        # self._loop = asyncio.get_event_loop()
        if self._type == "2":
            self._attr_brightness = action["value1"] * 2.55
        if self._type == "4":
            self._attr_current_cover_position = action["value1"]
            self._attr_is_closed = action["value1"] == 0

    @property
    def name(self):
        """A Niko Action state."""
        return self._name

    @property
    def state(self):
        """A Niko Action state."""
        return self._state

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
        return self._state != 0

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

    def is_cover(self) -> bool:
        """Is a cover."""
        return self.action_type == 4

    def is_light(self) -> bool:
        """Is a light."""
        return self.action_type == 1

    def is_dimmable(self) -> bool:
        """Is a dimmable light."""
        return self.action_type == 2

    def register_callback(self, callback) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    def update_state(self, state):
        """Update HA state."""
        if self.is_cover():
            self._attr_is_on = state > 0
            self._state = round(state)
            self._attr_is_closed = state == 0
            self._attr_current_cover_position = round(state)
        else:
            self._attr_is_on = state != 0
            if self.is_dimmable():
                self._attr_brightness = int(round(float(state) * 2.55))
        self.publish_updates()
