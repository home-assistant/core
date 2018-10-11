"""Common test utils for working with recorder component."""
from datetime import datetime
from uuid import uuid4

import json

from homeassistant.components.recorder import models


event_id_gen = 0


class MockEvent(models.Events):
    """Mock a recorder event."""

    def __init__(self, event_type, event_data={}, origin='LOCAL',
                 time_fired=None, created=None, context_id=None,
                 context_user_id=None, event_id=None):
        """Initialize the mock event."""
        global event_id_gen

        event_data = json.dumps(event_data)

        if event_id is None:
            event_id_gen += 1
            event_id = event_id_gen
        if time_fired is None:
            time_fired = datetime.utcnow()
        if created is None:
            created = time_fired
        if context_id is None:
            context_id = uuid4().hex

        super()
        self.event_id = 1
        self.event_type = event_type
        self.event_data = event_data
        self.origin = origin
        self.time_fired = time_fired
        self.created = created
        self.context_id = context_id
        self.context_user_id = context_user_id
