"""Handles state variable access and change notification."""

import logging

_LOGGER = logging.getLogger(__name__)


class State:
    """Class for state functions."""

    def __init__(self, hass, handler_func):
        """Initialize State."""

        self.hass = hass
        self.handler = handler_func
        #
        # notify message queues by variable
        #
        self.notify = {}

        #
        # Last value of state variable notifications.  We maintain this
        # so that trigger evaluation can use the last notified value,
        # rather than fetching the current value, which is subject to
        # race conditions multiple state variables are set.
        #
        self.notify_var_last = {}

    def notify_add(self, var_names, queue):
        """Register to notify state variables changes to be sent to queue."""

        for var_name in var_names if isinstance(var_names, list) else [var_names]:
            parts = var_name.split(".")
            if len(parts) != 2 and len(parts) != 3:
                continue
            state_var_name = f"{parts[0]}.{parts[1]}"
            if state_var_name not in self.notify:
                self.notify[state_var_name] = {}
            self.notify[state_var_name][queue] = var_names

    def notify_del(self, var_names, queue):
        """Unregister notify of state variables changes for given queue."""

        for var_name in var_names if isinstance(var_names, list) else [var_names]:
            parts = var_name.split(".")
            if len(parts) != 2 and len(parts) != 3:
                continue
            state_var_name = f"{parts[0]}.{parts[1]}"
            if (
                state_var_name not in self.notify
                or queue not in self.notify[state_var_name]
            ):
                return
            del self.notify[state_var_name][queue]

    async def update(self, new_vars, func_args):
        """Deliver all notifications for state variable changes."""

        _LOGGER.debug("state.update(%s, %s)", new_vars, func_args)
        notify = {}
        for var_name, var_val in new_vars.items():
            if var_name in self.notify:
                self.notify_var_last[var_name] = var_val
                notify.update(self.notify[var_name])

        for queue, var_names in notify.items():
            await queue.put(["state", [self.notify_var_get(var_names), func_args]])

    def notify_var_get(self, var_names):
        """Return the most recent value of a state variable change."""
        new_vars = {}
        for var_name in var_names if var_names is not None else []:
            if var_name in self.notify_var_last:
                new_vars[var_name] = self.notify_var_last[var_name]
        return new_vars

    def set(self, var_name, value, attributes=None):
        """Set a state variable and optional attributes in hass."""
        if len(var_name.split(".")) != 2:
            _LOGGER.error(
                "invalid variable name %s (should be 'domain.entity')", var_name
            )
            return
        _LOGGER.debug("setting %s = %s, attr = %s", var_name, value, attributes)
        self.hass.states.async_set(var_name, value, attributes)

    def exist(self, var_name):
        """Check if a state variable value or attribute exists in hass."""
        parts = var_name.split(".")
        if len(parts) != 2 and len(parts) != 3:
            return False
        value = self.hass.states.get(f"{parts[0]}.{parts[1]}")
        return value and (len(parts) == 2 or value.attributes.get(parts[2]) is not None)

    def get(self, var_name):
        """Get a state variable value or attribute from hass."""
        parts = var_name.split(".")
        if len(parts) != 2 and len(parts) != 3:
            return None
        value = self.hass.states.get(f"{parts[0]}.{parts[1]}")
        if not value:
            return None
        if len(parts) == 2:
            _LOGGER.debug("state.get %s = %s", var_name, value.state)
            return value.state
        return value.attributes.get(parts[2])

    def register_functions(self):
        """Register state functions."""
        functions = {
            "state.get": self.get,
            "state.set": self.set,
        }
        self.handler.register(functions)
