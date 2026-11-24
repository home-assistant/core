"""Tests for the Zonneplan actions."""

import dataclasses
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zonneplan.const import DOMAIN
from homeassistant.components.zonneplan.services import (
    ZonneplanService,
    ZonneplanServiceArgument,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from .conftest import MOCK_ACCOUNT


@pytest.mark.parametrize("interval", ["hour", "quarter"])
async def test_get_electricity_prices(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    interval: str,
) -> None:
    """Test getting the electricity prices."""
    response = await hass.services.async_call(
        DOMAIN,
        ZonneplanService.GET_ELECTRICITY_PRICES,
        {
            ZonneplanServiceArgument.CONFIG_ENTRY: init_integration.entry_id,
            ZonneplanServiceArgument.INTERVAL: interval,
        },
        blocking=True,
        return_response=True,
    )

    assert response == snapshot


async def test_get_electricity_prices_without_electricity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test getting the electricity prices of an account without electricity."""
    mock_zonneplan_client.async_get_account.return_value = dataclasses.replace(
        MOCK_ACCOUNT,
        address_groups=[
            dataclasses.replace(
                address_group,
                connections=[
                    connection
                    for connection in address_group.connections
                    if connection.market_segment != "electricity"
                ],
            )
            for address_group in MOCK_ACCOUNT.address_groups
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ZonneplanService.GET_ELECTRICITY_PRICES,
            {
                ZonneplanServiceArgument.CONFIG_ENTRY: mock_config_entry.entry_id,
                ZonneplanServiceArgument.INTERVAL: "hour",
            },
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "no_electricity_prices"


@pytest.mark.parametrize(
    ("entry_id", "translation_key"),
    [
        pytest.param(
            "01JXZKYZ00XZKYZ00XZKYZ00XZ",
            "service_config_entry_not_loaded",
            id="not_loaded",
        ),
        pytest.param(
            "unknown_entry_id", "service_config_entry_not_found", id="not_found"
        ),
    ],
)
async def test_get_electricity_prices_invalid_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entry_id: str,
    translation_key: str,
) -> None:
    """Test getting the electricity prices of a missing or unloaded config entry."""
    assert await async_setup_component(hass, DOMAIN, {})
    # Added after setup, so the entry stays not loaded.
    mock_config_entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            ZonneplanService.GET_ELECTRICITY_PRICES,
            {
                ZonneplanServiceArgument.CONFIG_ENTRY: entry_id,
                ZonneplanServiceArgument.INTERVAL: "hour",
            },
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == translation_key
