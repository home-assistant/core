"""Tests for the Zeversolar coordinator."""

from unittest.mock import patch

import pytest

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.components.zeversolar.coordinator import ZeversolarCoordinator
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"


async def test_update_raises_update_failed_on_error(hass: HomeAssistant) -> None:
    """_async_update_data wraps exceptions in UpdateFailed."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: MOCK_HOST})
    entry.add_to_hass(hass)
    coordinator = ZeversolarCoordinator(hass, entry)

    with (
        patch(
            "zeversolar.ZeverSolarClient.get_data",
            side_effect=Exception("network error"),
        ),
        pytest.raises(UpdateFailed, match="Cannot reach inverter"),
    ):
        await coordinator._async_update_data()
