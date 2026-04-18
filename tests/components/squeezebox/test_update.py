"""Test squeezebox update platform."""

import copy
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.squeezebox.const import (
    SENSOR_UPDATE_INTERVAL,
    STATUS_UPDATE_NEWPLUGINS,
)
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import FAKE_QUERY_RESPONSE

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update_lms(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.UPDATE],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("update.fakelib_lyrion_music_server")

    assert state is not None
    assert state.state == STATE_ON


async def test_update_plugins_install_fallback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states and attributes."""

    entity_id = "update.fakelib_updated_plugins"
    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.UPDATE],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    polltime = 30
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=False,
        ),
        patch(
            "homeassistant.components.squeezebox.update.POLL_AFTER_INSTALL",
            polltime,
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS]

    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_status",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=polltime + 1),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    attrs = state.attributes
    assert not attrs[ATTR_IN_PROGRESS]


async def test_update_plugins_install_restart_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states and attributes."""

    entity_id = "update.fakelib_updated_plugins"
    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.UPDATE],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=True,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    attrs = state.attributes
    assert not attrs[ATTR_IN_PROGRESS]


async def test_update_plugins_install_ok(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states and attributes."""

    entity_id = "update.fakelib_updated_plugins"
    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.UPDATE],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=False,
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS]

    resp = copy.deepcopy(FAKE_QUERY_RESPONSE)
    del resp[STATUS_UPDATE_NEWPLUGINS]

    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_status",
            return_value=resp,
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=SENSOR_UPDATE_INTERVAL + 1),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    attrs = state.attributes
    assert not attrs[ATTR_IN_PROGRESS]
