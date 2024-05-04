"""Tests for Fritz!Tools update platform."""

from unittest.mock import patch

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_FB_SERVICES,
    MOCK_FIRMWARE_AVAILABLE,
    MOCK_FIRMWARE_RELEASE_URL,
    MOCK_USER_DATA,
)

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

AVAILABLE_UPDATE = {
    "UserInterface1": {
        "GetInfo": {
            "NewX_AVM-DE_Version": MOCK_FIRMWARE_AVAILABLE,
            "NewX_AVM-DE_InfoURL": MOCK_FIRMWARE_RELEASE_URL,
        },
    }
}


async def test_update_entities_initialized(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test update entities."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    updates = hass.states.async_all(UPDATE_DOMAIN)
    assert len(updates) == 1


async def test_update_available(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test update entities."""

    fc_class_mock().override_services({**MOCK_FB_SERVICES, **AVAILABLE_UPDATE})

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    update = hass.states.get("update.mock_title_fritz_os")
    assert update is not None
    assert update.state == "on"
    assert update.attributes.get("installed_version") == "7.29"
    assert update.attributes.get("latest_version") == MOCK_FIRMWARE_AVAILABLE
    assert update.attributes.get("release_url") == MOCK_FIRMWARE_RELEASE_URL


async def test_no_update_available(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test update entities."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    update = hass.states.get("update.mock_title_fritz_os")
    assert update is not None
    assert update.state == "off"
    assert update.attributes.get("installed_version") == "7.29"
    assert update.attributes.get("latest_version") == "7.29"


async def test_available_update_can_be_installed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test update entities."""

    fc_class_mock().override_services({**MOCK_FB_SERVICES, **AVAILABLE_UPDATE})

    with patch(
        "homeassistant.components.fritz.common.FritzBoxTools.async_trigger_firmware_update",
        return_value=True,
    ) as mocked_update_call:
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        update = hass.states.get("update.mock_title_fritz_os")
        assert update is not None
        assert update.state == "on"

        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.mock_title_fritz_os"},
            blocking=True,
        )
        mocked_update_call.assert_called_once()
