"""Define tests for the AEMET OpenData init."""

from unittest.mock import AsyncMock, MagicMock, patch

from aemet_opendata.exceptions import AemetTimeout, AuthError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components import persistent_notification as pn
from homeassistant.components.aemet.const import (
    CONF_API_KEY_DATE,
    CONF_API_KEY_REMINDER,
    CONF_RADAR_UPDATES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .util import async_init_integration, mock_api_call

CONFIG = {
    CONF_NAME: "aemet",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 40.30403754,
    CONF_LONGITUDE: -3.72935236,
}


async def test_unload_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test (un)loading the AEMET integration."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, unique_id="aemet_unique_id", data=CONFIG
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED

        assert await hass.config_entries.async_remove(config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("weather.aemet") is None
        assert entity_registry.async_get("weather.aemet") is None


async def test_update_options_reloads_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating options reloads the config entry."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, unique_id="aemet_unique_id", data=CONFIG
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        hass.config_entries.async_update_entry(
            config_entry, options={CONF_RADAR_UPDATES: True}
        )
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED
        assert config_entry.options[CONF_RADAR_UPDATES] is True


async def test_update_options_failed_reload_dismisses_reminder(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed reload after disabling reminders dismisses the reminder."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-03-30 12:00:00+00:00")
    entry = await async_init_integration(
        hass,
        data={CONF_API_KEY_DATE: "2021-01-01"},
        options={CONF_API_KEY_REMINDER: True},
    )
    notification_id = f"{DOMAIN}_api_key_expiry_{entry.entry_id}"
    assert notification_id in pn._async_get_or_create_notifications(hass)

    with patch.object(
        hass.config_entries, "async_reload", return_value=False
    ) as async_reload:
        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_API_KEY_REMINDER: False,
                CONF_RADAR_UPDATES: True,
            },
        )
        await hass.async_block_till_done()

    async_reload.assert_awaited_once_with(entry.entry_id)
    assert notification_id not in pn._async_get_or_create_notifications(hass)


async def test_update_options_failed_reload_cancels_pending_reminder(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed reload after disabling reminders cancels the timer."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    entry = await async_init_integration(
        hass,
        data={CONF_API_KEY_DATE: "2021-01-01"},
        options={CONF_API_KEY_REMINDER: True},
    )
    notification_id = f"{DOMAIN}_api_key_expiry_{entry.entry_id}"
    assert notification_id not in pn._async_get_or_create_notifications(hass)

    with patch.object(
        hass.config_entries, "async_reload", return_value=False
    ) as async_reload:
        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_API_KEY_REMINDER: False,
                CONF_RADAR_UPDATES: True,
            },
        )
        await hass.async_block_till_done()

    async_reload.assert_awaited_once_with(entry.entry_id)

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        freezer.move_to("2021-03-29 09:00:01+00:00")
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)

    assert notification_id not in pn._async_get_or_create_notifications(hass)


async def test_reauth_clears_reminder_through_update_listener(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauthentication clears reminders through the update listener."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-03-30 12:00:00+00:00")
    entry = await async_init_integration(
        hass,
        data={CONF_API_KEY_DATE: "2021-01-01"},
        options={CONF_API_KEY_REMINDER: True},
    )
    notification_id = f"{DOMAIN}_api_key_expiry_{entry.entry_id}"
    assert notification_id in pn._async_get_or_create_notifications(hass)

    mocked_aemet = MagicMock()
    mocked_aemet.select_coordinates = AsyncMock()

    with (
        patch(
            "homeassistant.components.aemet.AEMET.api_call",
            side_effect=mock_api_call,
        ),
        patch(
            "homeassistant.components.aemet.config_flow.AEMET",
            return_value=mocked_aemet,
        ),
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "new-key",
                CONF_API_KEY_DATE: "2021-03-30",
            },
        )
        await hass.async_block_till_done(wait_background_tasks=True)

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data[CONF_API_KEY] == "new-key"
        assert entry.data[CONF_API_KEY_DATE] == "2021-03-30"
        assert entry.state is ConfigEntryState.LOADED
        assert notification_id not in pn._async_get_or_create_notifications(hass)

        freezer.move_to("2021-04-01 00:00:01+00:00")
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)

    assert notification_id not in pn._async_get_or_create_notifications(hass)


@pytest.mark.parametrize("reminder_enabled", [False, True])
async def test_api_key_expiry_lifecycle(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reminder_enabled: bool,
) -> None:
    """Test expiry reminders and reauthentication are scheduled on setup."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="aemet_unique_id",
            data={
                **CONFIG,
                CONF_API_KEY_DATE: "2021-01-01",
            },
            options={CONF_API_KEY_REMINDER: reminder_enabled},
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        freezer.move_to("2021-03-29 09:00:01+00:00")
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

        notifications = pn._async_get_or_create_notifications(hass)
        if reminder_enabled:
            notification = notifications[
                f"{DOMAIN}_api_key_expiry_{config_entry.entry_id}"
            ]
            assert notification["title"] == "AEMET API key may be expiring soon"
            assert "is expected to expire" in notification["message"]
        else:
            assert not notifications

        freezer.move_to("2021-04-01 00:00:01+00:00")
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

        notifications = pn._async_get_or_create_notifications(hass)
        if reminder_enabled:
            notification = notifications[
                f"{DOMAIN}_api_key_expiry_{config_entry.entry_id}"
            ]
            assert notification["title"] == "AEMET API key expiry date passed"
            assert "may still accept the key" in notification["message"]
        else:
            assert not notifications

    assert not hass.config_entries.flow.async_progress()


async def test_api_key_reminder_dismissed_on_unload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the API key reminder is dismissed when the entry unloads."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="aemet_unique_id",
            data={
                **CONFIG,
                CONF_API_KEY_DATE: "2021-01-01",
            },
            options={CONF_API_KEY_REMINDER: True},
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        freezer.move_to("2021-03-29 09:00:01+00:00")
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert pn._async_get_or_create_notifications(hass)

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED

    assert not pn._async_get_or_create_notifications(hass)


async def test_init_town_not_found(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test TownNotFound when loading the AEMET integration."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "api-key",
                CONF_LATITUDE: "0.0",
                CONF_LONGITUDE: "0.0",
                CONF_NAME: "AEMET",
            },
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_init_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test AuthError when loading the AEMET integration."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AuthError,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "api-key",
                CONF_LATITUDE: "0.0",
                CONF_LONGITUDE: "0.0",
                CONF_NAME: "AEMET",
            },
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_init_api_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test API timeouts when loading the AEMET integration."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AemetTimeout,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "api-key",
                CONF_LATITUDE: "0.0",
                CONF_LONGITUDE: "0.0",
                CONF_NAME: "AEMET",
            },
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
