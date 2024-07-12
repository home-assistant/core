"""Tests for Motionblinds BLE entities."""

from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.motionblinds_ble.const import (
    ATTR_CONNECT,
    ATTR_DISCONNECT,
    ATTR_FAVORITE,
    ATTR_SPEED,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_platform


@pytest.mark.parametrize(
    ("platform", "entity"),
    [
        (Platform.COVER, None),
        (Platform.BUTTON, ATTR_CONNECT),
        (Platform.BUTTON, ATTR_DISCONNECT),
        (Platform.BUTTON, ATTR_FAVORITE),
        (Platform.SELECT, ATTR_SPEED),
    ],
)
async def test_entity_update(
    hass: HomeAssistant, platform: Platform, entity: str
) -> None:
    """Test updating entity using homeassistant.update_entity."""

    await async_setup_component(hass, HA_DOMAIN, {})
    _, name = await setup_platform(hass, [platform])

    with patch(
        "homeassistant.components.motionblinds_ble.entity.MotionDevice.status_query"
    ) as status_query:
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {
                ATTR_ENTITY_ID: f"{platform.name.lower()}.{name}"
                if platform is Platform.COVER
                else f"{platform.name.lower()}.{name}_{entity}"
            },
            blocking=True,
        )
        status_query.assert_called_once()
