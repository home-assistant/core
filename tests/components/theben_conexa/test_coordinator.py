"""Tests for the Theben Conexa coordinator."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.theben_conexa.const import DOMAIN
from homeassistant.components.theben_conexa.coordinator import SmgwSensorCoordinator
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry

TEST_CONFIG_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_coordinator_async_init_success(
    hass: HomeAssistant,
    mock_conexa_smgw: AsyncMock,
) -> None:
    """Test coordinator initialization creates the API client and schedules updates."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_DATA)
    entry.add_to_hass(hass)
    coordinator = SmgwSensorCoordinator(hass, entry)

    await coordinator.async_init()

    assert coordinator._api is mock_conexa_smgw
    assert coordinator.gateway_info is mock_conexa_smgw.gatewayInfo
    assert coordinator._scheduled_updates is not None


async def test_coordinator_async_init_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test coordinator initialization raises ConfigEntryNotReady when the gateway is unreachable."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_DATA)
    entry.add_to_hass(hass)
    coordinator = SmgwSensorCoordinator(hass, entry)

    with (
        patch(
            "homeassistant.components.theben_conexa.coordinator.checkNetworkConnection",
            side_effect=TimeoutError,
        ),
        pytest.raises(ConfigEntryNotReady, match="Device is not reachable"),
    ):
        await coordinator.async_init()
