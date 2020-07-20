"""Handles event firing and notification."""

import logging

_LOGGER = logging.getLogger(__name__)


class Event:
    """Defined event functions."""

    def __init__(self, hass):
        """Initialize Event."""

        self.hass = hass
        #
        # notify message queues by event type
        #
        self.notify = {}
        self.notify_remove = {}

    async def event_listener(self, event):
        """Listen callback for given event which updates any notifications."""

        _LOGGER.debug("event_listener(%s)", event)
        func_args = {
            "trigger_type": "event",
            "event_type": event.event_type,
        }
        func_args.update(event.data)
        await self.update(event.event_type, func_args)

    def notify_add(self, event_type, queue):
        """Register to notify for events of given type to be sent to queue."""

        if event_type not in self.notify:
            self.notify[event_type] = set()
            _LOGGER.debug("event.notify_add(%s) -> adding event listener", event_type)
            self.notify_remove[event_type] = self.hass.bus.async_listen(
                event_type, self.event_listener
            )
        self.notify[event_type].add(queue)

    def notify_del(self, event_type, queue):
        """Unregister to notify for events of given type for given queue."""

        if event_type not in self.notify or queue not in self.notify[event_type]:
            return
        self.notify[event_type].discard(queue)
        if len(self.notify[event_type]) == 0:
            self.notify_remove[event_type]()
            _LOGGER.debug("event.notify_del(%s) -> removing event listener", event_type)
            del self.notify_remove[event_type]

    async def update(self, event_type, func_args):
        """Deliver all notifications for an event of the given type."""

        _LOGGER.debug("event.update(%s, %s, %s)", event_type, vars, func_args)
        if event_type in self.notify:
            for queue in self.notify[event_type]:
                await queue.put(["event", func_args])
