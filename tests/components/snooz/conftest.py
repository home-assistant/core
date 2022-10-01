"""Snooz test fixtures and configuration."""
from __future__ import annotations

from unittest.mock import patch

from pysnooz.commands import SnoozCommandData
import pytest

from homeassistant.components.snooz import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.snooz import (
    SNOOZ_SERVICE_INFO_NOT_PAIRING,
    TEST_ADDRESS,
    TEST_PAIRING_TOKEN,
    MockSnoozClient,
    SnoozFixture,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture()
@pytest.mark.asyncio()
async def mock_connected_snooz(hass: HomeAssistant):
    """Mock a Snooz configuration entry and returns its fan entity."""

    ble_device = SNOOZ_SERVICE_INFO_NOT_PAIRING
    client = MockSnoozClient(
        ble_device.address
    )  # pylint: disable=abstract-class-instantiated

    with patch(
        "homeassistant.components.snooz.async_ble_device_from_address",
        return_value=ble_device,
    ), patch("pysnooz.device.establish_connection", return_value=client):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=TEST_ADDRESS,
            data={CONF_ADDRESS: TEST_ADDRESS, CONF_TOKEN: TEST_PAIRING_TOKEN},
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        data = hass.data[DOMAIN][entry.entry_id]
        assert data

        # set the initial state of the device to off - volume 0%
        # this will also make the mock device connected
        await data.device.async_execute_command(SnoozCommandData(on=False, volume=0))

        yield SnoozFixture(entry, client, data)
