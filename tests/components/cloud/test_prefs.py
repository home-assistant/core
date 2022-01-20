"""Test Cloud preferences."""
from unittest.mock import patch

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.cloud import const
from homeassistant.components.cloud.prefs import STORAGE_KEY, CloudPreferences

from tests.common import flush_store


async def test_set_username(hass):
    """Test we clear config if we set different username."""
    prefs = CloudPreferences(hass)
    await prefs.async_initialize()

    assert prefs.google_enabled

    await prefs.async_update(google_enabled=False)

    assert not prefs.google_enabled

    await prefs.async_set_username("new-username")

    assert prefs.google_enabled


async def test_set_username_migration(hass):
    """Test we not clear config if we had no username."""
    prefs = CloudPreferences(hass)

    with patch.object(prefs, "_empty_config", return_value=prefs._empty_config(None)):
        await prefs.async_initialize()

    assert prefs.google_enabled

    await prefs.async_update(google_enabled=False)

    assert not prefs.google_enabled

    await prefs.async_set_username("new-username")

    assert not prefs.google_enabled


async def test_set_new_username(hass, hass_storage):
    """Test if setting new username returns true."""
    hass_storage[STORAGE_KEY] = {"version": 1, "data": {"username": "old-user"}}

    prefs = CloudPreferences(hass)
    await prefs.async_initialize()

    assert not await prefs.async_set_username("old-user")

    assert await prefs.async_set_username("new-user")


async def test_load_invalid_cloud_user(hass, hass_storage):
    """Test loading cloud user with invalid storage."""
    hass_storage[STORAGE_KEY] = {"version": 1, "data": {"cloud_user": "non-existing"}}

    prefs = CloudPreferences(hass)
    await prefs.async_initialize()

    cloud_user_id = await prefs.get_cloud_user()

    assert cloud_user_id != "non-existing"

    cloud_user = await hass.auth.async_get_user(
        hass_storage[STORAGE_KEY]["data"]["cloud_user"]
    )

    assert cloud_user
    assert cloud_user.groups[0].id == GROUP_ID_ADMIN


async def test_setup_remove_cloud_user(hass, hass_storage):
    """Test creating and removing cloud user."""
    hass_storage[STORAGE_KEY] = {"version": 1, "data": {"cloud_user": None}}

    prefs = CloudPreferences(hass)
    await prefs.async_initialize()
    await prefs.async_set_username("user1")

    cloud_user = await hass.auth.async_get_user(await prefs.get_cloud_user())

    assert cloud_user
    assert cloud_user.groups[0].id == GROUP_ID_ADMIN

    await prefs.async_set_username("user2")

    cloud_user2 = await hass.auth.async_get_user(await prefs.get_cloud_user())

    assert cloud_user2
    assert cloud_user2.groups[0].id == GROUP_ID_ADMIN
    assert cloud_user2.id != cloud_user.id


async def test_migration_1_1_to_1_2(hass, hass_storage):
    """Test migration from version 1 to 1.2."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "data": {
            const.PREF_ENABLE_ALEXA: False,
            const.PREF_ENABLE_GOOGLE: False,
            const.PREF_ENABLE_REMOTE: True,
            const.PREF_GOOGLE_LOCAL_WEBHOOK_ID: "abc",
        },
    }

    prefs = CloudPreferences(hass)
    await prefs.async_initialize()

    # Test data was loaded and mmigrated
    assert prefs._prefs == {
        const.PREF_ALEXA_DEFAULT_EXPOSE: None,
        const.PREF_ALEXA_ENTITY_CONFIGS: {},
        const.PREF_ALEXA_REPORT_STATE: True,
        const.PREF_CLOUD_USER: None,
        const.PREF_CLOUDHOOKS: {},
        const.PREF_ENABLE_ALEXA: False,
        const.PREF_ENABLE_GOOGLE: False,
        const.PREF_ENABLE_REMOTE: True,
        const.PREF_GOOGLE_DEFAULT_EXPOSE: None,
        const.PREF_GOOGLE_ENTITY_CONFIGS: {},
        const.PREF_GOOGLE_LOCAL_WEBHOOK_ID: "abc",
        const.PREF_GOOGLE_REPORT_STATE: True,
        const.PREF_GOOGLE_SECURE_DEVICES_PIN: None,
        const.PREF_TTS_DEFAULT_VOICE: None,
        const.PREF_USERNAME: None,
    }

    # Update to trigger a store
    await prefs.async_update(remote_enabled=True)

    # Check we store migrated data
    await flush_store(prefs._store)
    assert hass_storage[STORAGE_KEY] == {
        "version": 1,
        "minor_version": 2,
        "key": STORAGE_KEY,
        "data": {
            const.PREF_ALEXA_DEFAULT_EXPOSE: None,
            const.PREF_ALEXA_ENTITY_CONFIGS: {},
            const.PREF_ALEXA_REPORT_STATE: True,
            const.PREF_CLOUD_USER: None,
            const.PREF_CLOUDHOOKS: {},
            const.PREF_ENABLE_ALEXA: False,
            const.PREF_ENABLE_GOOGLE: False,
            const.PREF_ENABLE_REMOTE: True,
            const.PREF_GOOGLE_DEFAULT_EXPOSE: None,
            const.PREF_GOOGLE_ENTITY_CONFIGS: {},
            const.PREF_GOOGLE_LOCAL_WEBHOOK_ID: "abc",
            const.PREF_GOOGLE_REPORT_STATE: True,
            const.PREF_GOOGLE_SECURE_DEVICES_PIN: None,
            const.PREF_TTS_DEFAULT_VOICE: None,
            const.PREF_USERNAME: None,
        },
    }
