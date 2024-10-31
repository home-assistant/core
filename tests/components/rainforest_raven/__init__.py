"""Tests for the Rainforest RAVEn component."""

from unittest.mock import AsyncMock

from homeassistant.components.rainforest_raven.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_MAC

from .const import (
    DEMAND,
    DEVICE_INFO,
    DISCOVERY_INFO,
    METER_INFO,
    METER_LIST,
    NETWORK_INFO,
    PRICE_CLUSTER,
    SUMMATION,
)

from tests.common import MockConfigEntry


def create_mock_device() -> AsyncMock:
    """Create a mock instance of RAVEnStreamDevice."""
    device = AsyncMock()

    device.__aenter__.return_value = device
    device.get_current_price.return_value = PRICE_CLUSTER
    device.get_current_summation_delivered.return_value = SUMMATION
    device.get_device_info.return_value = DEVICE_INFO
    device.get_instantaneous_demand.return_value = DEMAND
    device.get_meter_list.return_value = METER_LIST
    # pylint: disable-next=unnecessary-lambda
    device.get_meter_info.side_effect = lambda meter: METER_INFO.get(meter)
    device.get_network_info.return_value = NETWORK_INFO

    return device


def create_mock_entry(no_meters: bool = False) -> MockConfigEntry:
    """Create a mock config entry for a RAVEn device."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: DISCOVERY_INFO.device,
            CONF_MAC: [] if no_meters else [METER_INFO[None].meter_mac_id.hex()],
        },
        entry_id="01JADXBJSPYEBAFPKGXDJWZBQ8",
    )
