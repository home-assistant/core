"""Test Cloud preferences."""
from unittest.mock import patch

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.cloud.prefs import STORAGE_KEY, CloudPreferences


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
