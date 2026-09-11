"""Tests for the Traccar Server integration."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

from pytraccar import SubscriptionData


def get_subscription_callback(
    mock_traccar_api_client: AsyncMock,
) -> Callable[[SubscriptionData], Awaitable[None]]:
    """Return the callback our integration registered with client.subscribe().

    Reading it off the mock's call args exercises the exact function
    pytraccar would invoke, instead of calling a coordinator method by name.
    """
    return mock_traccar_api_client.subscribe.call_args.args[0]
