"""Tests for the Tesla Wall Connector coordinator."""

import asyncio
from functools import partial
from unittest.mock import MagicMock, patch

from tesla_wall_connector import WallConnector

from homeassistant.components.tesla_wall_connector.const import (
    WALLCONNECTOR_DATA_LIFETIME,
    WALLCONNECTOR_DATA_VITALS,
    WALLCONNECTOR_DATA_WIFI_STATUS,
)
from homeassistant.core import HomeAssistant

from .conftest import (
    create_wall_connector_entry,
    get_default_version_data,
    get_lifetime_mock,
    get_vitals_mock,
    get_wifi_status_mock,
)


async def test_requests_do_not_overlap(hass: HomeAssistant) -> None:
    """A device that cannot handle concurrent requests can still be polled."""
    request_active = False

    async def fetch[T](data: T) -> T:
        nonlocal request_active
        assert not request_active
        request_active = True
        try:
            await asyncio.sleep(0)
            return data
        finally:
            request_active = False

    vitals = get_vitals_mock()
    lifetime = get_lifetime_mock()
    wifi_status = get_wifi_status_mock()
    client = MagicMock(spec=WallConnector)
    client.async_get_vitals.side_effect = partial(fetch, vitals)
    client.async_get_lifetime.side_effect = partial(fetch, lifetime)
    client.async_get_wifi_status.side_effect = partial(fetch, wifi_status)
    client.async_get_version.return_value = get_default_version_data()
    with patch(
        "homeassistant.components.tesla_wall_connector.WallConnector",
        return_value=client,
    ):
        entry = await create_wall_connector_entry(hass)

    coordinator = entry.runtime_data.update_coordinator

    assert coordinator.last_update_success
    assert coordinator.data == {
        WALLCONNECTOR_DATA_VITALS: vitals,
        WALLCONNECTOR_DATA_LIFETIME: lifetime,
        WALLCONNECTOR_DATA_WIFI_STATUS: wifi_status,
    }
    client.async_get_vitals.assert_awaited_once()
    client.async_get_lifetime.assert_awaited_once()
    client.async_get_wifi_status.assert_awaited_once()
