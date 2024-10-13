"""Test the Rainforest Eagle diagnostics."""

from dataclasses import asdict

import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from . import create_mock_entry
from .const import DEMAND, NETWORK_INFO, PRICE_CLUSTER, SUMMATION

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def mock_entry_no_meters(hass: HomeAssistant, mock_device):
    """Mock a RAVEn config entry with no meters."""
    mock_entry = create_mock_entry(True)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry


async def test_entry_diagnostics_no_meters(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_device,
    mock_entry_no_meters,
) -> None:
    """Test RAVEn diagnostics before the coordinator has updated."""
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_entry_no_meters
    )

    config_entry_dict = mock_entry_no_meters.as_dict()
    config_entry_dict["data"][CONF_MAC] = REDACTED

    assert result == {
        "config_entry": config_entry_dict | {"discovery_keys": {}},
        "data": {
            "Meters": {},
            "NetworkInfo": {**asdict(NETWORK_INFO), "device_mac_id": REDACTED},
        },
    }


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_device, mock_entry
) -> None:
    """Test RAVEn diagnostics."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)

    config_entry_dict = mock_entry.as_dict()
    config_entry_dict["data"][CONF_MAC] = REDACTED

    assert result == {
        "config_entry": config_entry_dict | {"discovery_keys": {}},
        "data": {
            "Meters": {
                "**REDACTED0**": {
                    "CurrentSummationDelivered": {
                        **asdict(SUMMATION),
                        "device_mac_id": REDACTED,
                        "meter_mac_id": REDACTED,
                    },
                    "InstantaneousDemand": {
                        **asdict(DEMAND),
                        "device_mac_id": REDACTED,
                        "meter_mac_id": REDACTED,
                    },
                    "PriceCluster": {
                        **asdict(PRICE_CLUSTER),
                        "device_mac_id": REDACTED,
                        "meter_mac_id": REDACTED,
                        "currency": {
                            "__type": str(type(PRICE_CLUSTER.currency)),
                            "repr": repr(PRICE_CLUSTER.currency),
                        },
                    },
                },
            },
            "NetworkInfo": {**asdict(NETWORK_INFO), "device_mac_id": REDACTED},
        },
    }
