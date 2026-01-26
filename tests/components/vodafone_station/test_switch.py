"""Tests for Vodafone Station switch platform."""

from unittest.mock import AsyncMock, patch

from aiovodafone.const import WIFI_DATA
from aiovodafone.exceptions import (
    AlreadyLogged,
    CannotAuthenticate,
    CannotConnect,
    GenericLoginError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TOGGLE
from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.components.vodafone_station.coordinator import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import setup_integration
from .const import TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.vodafone_station.PLATFORMS", [Platform.SWITCH]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("wifi_key", "wifi_name", "wifi_state"),
    [
        ("guest", "guest_network", "on"),
        ("guest_5g", "guest_5ghz_network", "off"),
    ],
)
async def test_switch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    wifi_key: str,
    wifi_name: str,
    wifi_state: str,
) -> None:
    """Test switch."""

    mock_vodafone_station_router.get_wifi_data.return_value = {
        WIFI_DATA: {
            f"{wifi_key}": {
                "on": 1 if wifi_state == "on" else 0,
                "ssid": f"{wifi_name}",
            }
        }
    }

    await setup_integration(hass, mock_config_entry)

    entity_id = f"switch.vodafone_station_{TEST_SERIAL_NUMBER}_{slugify(wifi_name)}"
    assert (state := hass.states.get(entity_id))
    assert state.state == wifi_state

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_vodafone_station_router.set_wifi_status.call_count == 1

    mock_vodafone_station_router.get_wifi_data.return_value = {
        WIFI_DATA: {
            f"{wifi_key}": {
                "on": 0 if wifi_state == "on" else 1,
                "ssid": f"{wifi_name}",
            }
        }
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ("off" if wifi_state == "on" else "on")


@pytest.mark.parametrize(
    ("side_effect", "key", "error"),
    [
        (CannotConnect, "cannot_execute_action", "CannotConnect()"),
        (AlreadyLogged, "cannot_execute_action", "AlreadyLogged()"),
        (GenericLoginError, "cannot_execute_action", "GenericLoginError()"),
        (CannotAuthenticate, "cannot_authenticate", "CannotAuthenticate()"),
    ],
)
async def test_switch_fails(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    key: str,
    error: str,
) -> None:
    """Test switch action fails."""

    await setup_integration(hass, mock_config_entry)

    mock_vodafone_station_router.set_wifi_status.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {
                ATTR_ENTITY_ID: f"switch.vodafone_station_{TEST_SERIAL_NUMBER}_guest_5ghz_network"
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == key
    assert exc_info.value.translation_placeholders == {"error": error}
