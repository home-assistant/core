"""Test functions in utils module."""

from homeassistant.components.igloohome.utils import get_linked_bridge

from .conftest import (
    GET_DEVICE_INFO_RESPONSE_BRIDGE_LINKED_LOCK,
    GET_DEVICE_INFO_RESPONSE_BRIDGE_NO_LINKED_DEVICE,
    GET_DEVICE_INFO_RESPONSE_LOCK,
)


def test_get_linked_bridge_expect_bridge_id_returned() -> None:
    """Test that get_linked_bridge returns the bridge ID."""
    assert (
        get_linked_bridge(
            GET_DEVICE_INFO_RESPONSE_LOCK.deviceId,
            [GET_DEVICE_INFO_RESPONSE_BRIDGE_LINKED_LOCK],
        )
        == GET_DEVICE_INFO_RESPONSE_BRIDGE_LINKED_LOCK.deviceId
    )


def test_get_linked_bridge_expect_none_returned() -> None:
    """Test that get_linked_bridge returns None."""
    assert (
        get_linked_bridge(
            GET_DEVICE_INFO_RESPONSE_LOCK.deviceId,
            [GET_DEVICE_INFO_RESPONSE_BRIDGE_NO_LINKED_DEVICE],
        )
        is None
    )
