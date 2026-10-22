"""Check config flow device validation without retaining subscriptions."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import replace
from unittest.mock import Mock, patch

from lorawan_connection import ConnectionUnavailable, DeviceEvent, Unsubscribe
import pytest

from homeassistant.components.lorawan import (
    NoConnectionsError,
    NoSupportedDevicesError,
    async_validate_devices,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import RegisterBackend
from .helpers import DESCRIPTOR, ExampleDevices


async def test_no_connections(hass: HomeAssistant) -> None:
    """An initialized registry without connections cannot validate devices."""
    assert await async_setup_component(hass, "lorawan", {})
    with pytest.raises(NoConnectionsError):
        await async_validate_devices(hass, create_collection=ExampleDevices)


@pytest.mark.parametrize(
    ("supported", "outcome"),
    [(True, nullcontext()), (False, pytest.raises(NoSupportedDevicesError))],
)
async def test_matching_devices(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    supported: bool,
    outcome: AbstractContextManager[object],
) -> None:
    """Release the probe and preserve the connection for success and no match."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    collection = ExampleDevices(backend)
    is_supported = Mock(return_value=supported)
    factory = Mock(return_value=collection)
    unsubscribe = Mock()
    async_subscribe = backend.async_subscribe

    async def subscribe(
        *,
        brands: frozenset[tuple[str, int | str]] | None,
        listener: Callable[[DeviceEvent], None],
    ) -> Unsubscribe:
        unsubscribe.side_effect = await async_subscribe(
            brands=brands, listener=listener
        )
        return unsubscribe

    with patch.object(backend, "async_subscribe", side_effect=subscribe), outcome:
        await async_validate_devices(
            hass, create_collection=factory, is_supported=is_supported
        )
    factory.assert_called_once_with(backend)
    is_supported.assert_called_once()
    assert is_supported.call_args.args[0].closed
    assert not collection.devices
    unsubscribe.assert_called_once_with()
    assert len(backend._disconnect_listeners) == 1
    assert await async_validate_devices(hass, create_collection=ExampleDevices) is None


@pytest.mark.parametrize("error", [None, ConnectionUnavailable])
async def test_later_connection(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    error: type[ConnectionUnavailable] | None,
) -> None:
    """Keep checking when a preceding connection is empty or unavailable."""
    first, _ = await registered_backend("first", [])
    await registered_backend("second", [replace(DESCRIPTOR, network_id="second")])
    with patch.object(
        first, "async_subscribe", wraps=first.async_subscribe, side_effect=error
    ):
        await async_validate_devices(hass, create_collection=ExampleDevices)


async def test_unavailable_connection(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
) -> None:
    """A registered connection that cannot replay devices is unavailable."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    with (
        patch.object(backend, "async_subscribe", side_effect=ConnectionUnavailable),
        pytest.raises(NoConnectionsError),
    ):
        await async_validate_devices(hass, create_collection=ExampleDevices)
    assert len(backend._disconnect_listeners) == 1


async def test_empty_and_unavailable_connections(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
) -> None:
    """An empty usable connection means no supported devices were found."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    await registered_backend("empty", [])
    with (
        patch.object(backend, "async_subscribe", side_effect=ConnectionUnavailable),
        pytest.raises(NoSupportedDevicesError),
    ):
        await async_validate_devices(hass, create_collection=ExampleDevices)
    assert len(backend._disconnect_listeners) == 1


@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError])
async def test_interrupted_validation(
    hass: HomeAssistant,
    registered_backend: RegisterBackend,
    error: type[Exception | asyncio.CancelledError],
) -> None:
    """Release probe subscriptions when validation fails or is canceled."""
    backend, _ = await registered_backend("network", [DESCRIPTOR])
    with (
        patch.object(backend, "async_subscribe", side_effect=error) as subscribe,
        pytest.raises(error),
    ):
        await async_validate_devices(hass, create_collection=ExampleDevices)
    subscribe.assert_awaited_once()
    assert len(backend._disconnect_listeners) == 1
