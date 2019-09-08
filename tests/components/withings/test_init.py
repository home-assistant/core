"""Tests for the Withings component."""
from asynctest import MagicMock
import voluptuous as vol

import homeassistant.components.api as api
import homeassistant.components.http as http
from homeassistant.components.withings import async_setup, const, CONFIG_SCHEMA

from .conftest import WithingsFactory, WithingsFactoryConfig

BASE_HASS_CONFIG = {
    http.DOMAIN: {},
    api.DOMAIN: {"base_url": "http://localhost/"},
    const.DOMAIN: None,
}


def config_schema_validate(withings_config):
    """Assert a schema config succeeds."""
    hass_config = BASE_HASS_CONFIG.copy()
    hass_config[const.DOMAIN] = withings_config

    return CONFIG_SCHEMA(hass_config)


def config_schema_assert_fail(withings_config):
    """Assert a schema config will fail."""
    try:
        config_schema_validate(withings_config)
        assert False, "This line should not have run."
    except vol.error.MultipleInvalid:
        assert True


def test_config_schema_basic_config():
    """Test schema."""
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 2"],
        }
    )


def test_config_schema_client_id():
    """Test schema."""
    config_schema_assert_fail(
        {
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 2"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_SECRET: "my_client_secret",
            const.CLIENT_ID: "",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_SECRET: "my_client_secret",
            const.CLIENT_ID: "my_client_id",
            const.PROFILES: ["Person 1"],
        }
    )


def test_config_schema_client_secret():
    """Test schema."""
    config_schema_assert_fail(
        {const.CLIENT_ID: "my_client_id", const.PROFILES: ["Person 1"]}
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1"],
        }
    )


def test_config_schema_profiles():
    """Test schema."""
    config_schema_assert_fail(
        {const.CLIENT_ID: "my_client_id", const.CLIENT_SECRET: "my_client_secret"}
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: "",
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: [],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1", "Person 2"],
        }
    )


def test_config_schema_base_url():
    """Test schema."""
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: 123,
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: "",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_assert_fail(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: "blah blah",
            const.PROFILES: ["Person 1"],
        }
    )
    config_schema_validate(
        {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.BASE_URL: "https://www.blah.blah.blah/blah/blah",
            const.PROFILES: ["Person 1"],
        }
    )


async def test_async_setup_no_config(hass):
    """Test method."""
    hass.async_create_task = MagicMock()

    await async_setup(hass, {})

    hass.async_create_task.assert_not_called()


async def test_async_setup_teardown(withings_factory: WithingsFactory, hass):
    """Test method."""
    data = await withings_factory(WithingsFactoryConfig(measures=[const.MEAS_TEMP_C]))

    profile = WithingsFactoryConfig.PROFILE_1
    await data.configure_all(profile, "authorization_code")

    entries = hass.config_entries.async_entries(const.DOMAIN)
    assert entries

    for entry in entries:
        await hass.config_entries.async_unload(entry.entry_id)
