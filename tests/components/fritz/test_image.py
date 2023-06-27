"""Tests for Fritz!Tools image platform."""
import pytest

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.setup import async_setup_component

from .const import MOCK_FB_SERVICES, MOCK_USER_DATA

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

GUEST_WIFI_ENABLED: dict[str, dict] = {
    "WLANConfiguration0": {
        "GetInfo": {
            "NewEnable": True,
            "NewSSID": "HomeWifi",
        }
    },
    "WLANConfiguration1": {
        "GetInfo": {
            "NewEnable": True,
            "NewSSID": "GuestWifi",
        }
    },
}

GUEST_WIFI_DISABLED: dict[str, dict] = {
    "WLANConfiguration0": {
        "GetInfo": {
            "NewEnable": True,
            "NewSSID": "HomeWifi",
        }
    },
    "WLANConfiguration1": {
        "GetInfo": {
            "NewEnable": False,
            "NewSSID": "GuestWifi",
        }
    },
}


@pytest.mark.parametrize(("fc_data"), [({**MOCK_FB_SERVICES, **GUEST_WIFI_ENABLED})])
async def test_image_entities_initialized(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test image entities."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    images = hass.states.async_all(IMAGE_DOMAIN)
    assert len(images) == 1
    assert images[0].name == "Mock Title GuestWifi"

    entity_registry = async_get_entity_registry(hass)
    entity_entry = entity_registry.async_get("image.mock_title_guestwifi")

    assert entity_entry.unique_id == "1c_ed_6f_12_34_11_guestwifi_qr_code"


@pytest.mark.parametrize(("fc_data"), [({**MOCK_FB_SERVICES, **GUEST_WIFI_DISABLED})])
async def test_image_guest_wifi_disabled(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test image entities."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    images = hass.states.async_all(IMAGE_DOMAIN)
    assert len(images) == 0
