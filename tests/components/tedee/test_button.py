"""Tests for the Tedee Buttons."""


from unittest.mock import MagicMock

from pytedee_async import TedeeClientException
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.tedee.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_unlock(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the tedee unlatch button."""
    mock_tedee.pull.return_value = None

    state = hass.states.get("button.lock_1a2b_pull_latch")
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Lock-1A2B Pull latch"
    assert state.attributes.get(ATTR_ICON) == "mdi:gesture-tap-button"
    assert state

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345-unlatch-button"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, 12345)}
    assert device.manufacturer == "tedee"
    assert device.name == "Lock-1A2B"
    assert device.model == "Tedee PRO"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.lock_1a2b_pull_latch",
        },
        blocking=True,
    )

    assert len(mock_tedee.pull.mock_calls) == 1
    mock_tedee.pull.assert_called_once()

    mock_tedee.pull.side_effect = TedeeClientException("Boom")
    with pytest.raises(
        HomeAssistantError,
        match="Error while unlatching the lock 12345 through button: Boom",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.lock_1a2b_pull_latch",
            },
            blocking=True,
        )


async def test_unlock_unlatch(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the tedee unlock & unlatch button."""
    mock_tedee.open.return_value = None

    state = hass.states.get("button.lock_1a2b_unlock_and_pull_latch")
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Lock-1A2B Unlock and pull latch"
    assert state.attributes.get(ATTR_ICON) == "mdi:gesture-tap-button"
    assert state

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345-unlockunlatch-button"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, 12345)}
    assert device.manufacturer == "tedee"
    assert device.name == "Lock-1A2B"
    assert device.model == "Tedee PRO"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.lock_1a2b_unlock_and_pull_latch",
        },
        blocking=True,
    )

    assert len(mock_tedee.open.mock_calls) == 1
    mock_tedee.open.assert_called_once()
