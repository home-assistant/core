"""Platform-agnostic push subscriptions for mobile_app.

An app registers a push token against a set of entity_ids; the integration sends
a silent push to that token whenever any of those entities change state. Used by
the iOS companion app to keep WidgetKit timelines in sync, but the contract is
deliberately platform-neutral: an app says "here is my token, push to it when
these entities change". Core has no knowledge of widgets.
"""

# Imported so the webhook command registrations in the submodule run on import.
from . import webhook  # noqa: F401
from .store import (
    async_restore_push_subscriptions,
    async_teardown_device_subscriptions,
    remove_push_subscription,
    remove_stored_device_subscriptions,
    store_push_subscription,
)

__all__ = [
    "async_restore_push_subscriptions",
    "async_teardown_device_subscriptions",
    "remove_push_subscription",
    "remove_stored_device_subscriptions",
    "store_push_subscription",
]
