"""Tests for the Hot Spring water heater platform."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError, Spa, SpaInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry

ENTITY_ID = "water_heater.connectedspa_ddeeff"


async def test_water_heater_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the water heater entity state."""
    state = hass.states.get(ENTITY_ID)
    assert state == snapshot

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry == snapshot


async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test setting target temperature."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 38,
        },
        blocking=True,
    )

    mock_hotspring.set_temperature.assert_called_once_with(100.4)


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (HotSpringConnectionError, "Error communicating with Hot Spring API"),
        (HotSpringError, "Invalid response from Hot Spring API"),
    ],
)
async def test_set_temperature_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when setting target temperature."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    mock_hotspring.set_temperature.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 38,
            },
            blocking=True,
        )


async def test_water_heater_no_mac_address(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the water heater entity when mac_address is not available."""
    device_fixture.info = SpaInfo(
        hostname="ConnectedSpa_DDEEFF",
        root_topic="unknownTopic123",
        sna_ready=True,
        brand_name="Hot Spring",
        collection_type="Highlife",
        model_type="Relay",
        volume=335,
    )
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == "unknownTopic123_water_heater"

    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert (DOMAIN, "unknownTopic123") in device.identifiers
    assert not device.connections
