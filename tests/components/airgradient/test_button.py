"""Tests for the AirGradient button platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from airgradient import Config
from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.airgradient.const import DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    airgradient_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_pressing_button(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing button."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.airgradient_calibrate_co2_sensor",
        },
        blocking=True,
    )
    mock_airgradient_client.request_co2_calibration.assert_called_once()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.airgradient_test_led_bar",
        },
        blocking=True,
    )
    mock_airgradient_client.request_led_bar_test.assert_called_once()


async def test_cloud_creates_no_button(
    hass: HomeAssistant,
    mock_cloud_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cloud configuration control."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all()) == 0

    mock_cloud_airgradient_client.get_config.return_value = Config.from_json(
        load_fixture("get_config_local.json", DOMAIN)
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    mock_cloud_airgradient_client.get_config.return_value = Config.from_json(
        load_fixture("get_config_cloud.json", DOMAIN)
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
