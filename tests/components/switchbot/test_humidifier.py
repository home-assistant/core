"""Test the switchbot humidifiers."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_AUTO,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SENSOR_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import WOHUMIDIFIER_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_humidifier_set_humidity(hass: HomeAssistant) -> None:
    """Test setting humidity on the SwitchBot humidifier."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOHUMIDIFIER_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "humidifier",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with patch(
        "switchbot.SwitchbotHumidifier.set_level", new=AsyncMock(return_value=True)
    ) as mock_set_level:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "humidifier.test_name"

        # Test set humidity
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: entity_id, ATTR_HUMIDITY: 60},
            blocking=True,
        )
        mock_set_level.assert_awaited_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_humidifier_set_mode(hass: HomeAssistant) -> None:
    """Test setting mode on the SwitchBot humidifier."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOHUMIDIFIER_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "humidifier",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "switchbot.SwitchbotHumidifier.async_set_auto",
            new=AsyncMock(return_value=True),
        ) as mock_set_auto,
        patch(
            "switchbot.SwitchbotHumidifier.async_set_manual",
            new=AsyncMock(return_value=True),
        ) as mock_set_manual,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "humidifier.test_name"

        assert hass.states.get(entity_id).attributes[ATTR_MODE] == MODE_NORMAL

        # Test set auto mode
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_MODE: MODE_AUTO},
            blocking=True,
        )
        mock_set_auto.assert_awaited_once()

        # Test set normal mode
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_MODE: MODE_NORMAL},
            blocking=True,
        )
        mock_set_manual.assert_awaited_once()
