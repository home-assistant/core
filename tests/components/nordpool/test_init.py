"""Test for Nord Pool component Init."""

from __future__ import annotations

import json
from unittest.mock import patch

from pynordpool import (
    API,
    NordPoolClient,
    NordPoolConnectionError,
    NordPoolEmptyResponseError,
    NordPoolError,
    NordPoolResponseError,
)
import pytest

from homeassistant.components.nordpool.const import CONF_AREAS, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.freeze_time("2024-11-05T10:00:00+00:00")
async def test_unload_entry(hass: HomeAssistant, get_client: NordPoolClient) -> None:
    """Test load and unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error"),
    [
        (NordPoolConnectionError),
        (NordPoolEmptyResponseError),
        (NordPoolError),
        (NordPoolResponseError),
    ],
)
async def test_initial_startup_fails(
    hass: HomeAssistant, get_client: NordPoolClient, error: Exception
) -> None:
    """Test load and unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=error,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time("2024-11-05T10:00:00+00:00")
async def test_reconfigure_cleans_up_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_client: NordPoolClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test clean up devices due to reconfiguration."""
    nl_json_file = load_fixture("delivery_period_nl.json", DOMAIN)
    load_nl_json = json.loads(nl_json_file)

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED

    assert device_registry.async_get_device(identifiers={(DOMAIN, "SE3")})
    assert device_registry.async_get_device(identifiers={(DOMAIN, "SE4")})
    assert entity_registry.async_get("sensor.nord_pool_se3_current_price")
    assert entity_registry.async_get("sensor.nord_pool_se4_current_price")
    assert hass.states.get("sensor.nord_pool_se3_current_price")
    assert hass.states.get("sensor.nord_pool_se4_current_price")

    aioclient_mock.clear_requests()
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2024-11-04",
            "market": "DayAhead",
            "deliveryArea": "NL",
            "currency": "EUR",
        },
        json=load_nl_json,
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2024-11-05",
            "market": "DayAhead",
            "deliveryArea": "NL",
            "currency": "EUR",
        },
        json=load_nl_json,
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2024-11-06",
            "market": "DayAhead",
            "deliveryArea": "NL",
            "currency": "EUR",
        },
        json=load_nl_json,
    )

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AREAS: ["NL"],
            CONF_CURRENCY: "EUR",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        "areas": [
            "NL",
        ],
        "currency": "EUR",
    }
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get_device(identifiers={(DOMAIN, "NL")})
    assert entity_registry.async_get("sensor.nord_pool_nl_current_price")
    assert hass.states.get("sensor.nord_pool_nl_current_price")

    assert not device_registry.async_get_device(identifiers={(DOMAIN, "SE3")})
    assert not entity_registry.async_get("sensor.nord_pool_se3_current_price")
    assert not hass.states.get("sensor.nord_pool_se3_current_price")
    assert not device_registry.async_get_device(identifiers={(DOMAIN, "SE4")})
    assert not entity_registry.async_get("sensor.nord_pool_se4_current_price")
    assert not hass.states.get("sensor.nord_pool_se4_current_price")
