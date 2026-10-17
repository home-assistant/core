"""Test the NZBGet switches."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.nzbget.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import ENTRY_OPTIONS, init_integration

from tests.common import MockConfigEntry


async def test_download_switch(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, nzbget_api: MagicMock
) -> None:
    """Test the creation and values of the download switch."""
    instance = nzbget_api.return_value

    entry = await init_integration(hass)
    assert entry

    entity_id = "switch.nzbgettest_download"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.unique_id == f"{entry.entry_id}_download"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    # test download paused
    instance.status.return_value["DownloadPaused"] = True

    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_download_switch_services(
    hass: HomeAssistant, nzbget_api: MagicMock
) -> None:
    """Test download switch services."""
    instance = nzbget_api.return_value

    entry = await init_integration(hass)
    entity_id = "switch.nzbgettest_download"
    assert entry

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    instance.pausedownload.assert_called_once()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    instance.resumedownload.assert_called_once()


@pytest.mark.usefixtures("nzbget_api")
async def test_switch_name_from_entry_title(hass: HomeAssistant) -> None:
    """Test the switch is named from the entry title when no legacy name is stored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.10.30",
        data={
            CONF_HOST: "10.10.10.30",
            CONF_PASSWORD: "",
            CONF_PORT: 6789,
            CONF_SSL: False,
            CONF_USERNAME: "",
            CONF_VERIFY_SSL: False,
        },
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.10_10_10_30_download")
    assert state
    assert state.name == "10.10.10.30 Download"
