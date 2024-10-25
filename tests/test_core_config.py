"""Test core_config."""

from collections import OrderedDict
import copy
from typing import Any
from unittest.mock import patch

import pytest
from voluptuous import Invalid, MultipleInvalid

from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_FRIENDLY_NAME,
    CONF_AUTH_MFA_MODULES,
    CONF_AUTH_PROVIDERS,
    CONF_CUSTOMIZE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import ConfigSource, HomeAssistant, State
from homeassistant.core_config import (
    _CUSTOMIZE_DICT_SCHEMA,
    CORE_CONFIG_SCHEMA,
    DATA_CUSTOMIZE,
    _validate_stun_or_turn_url,
    async_process_ha_core_config,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import Entity
from homeassistant.util import webrtc as webrtc_util
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .common import MockUser


def test_core_config_schema() -> None:
    """Test core config schema."""
    for value in (
        {"unit_system": "K"},
        {"time_zone": "non-exist"},
        {"latitude": "91"},
        {"longitude": -181},
        {"external_url": "not an url"},
        {"internal_url": "not an url"},
        {"currency", 100},
        {"customize": "bla"},
        {"customize": {"light.sensor": 100}},
        {"customize": {"entity_id": []}},
        {"country": "xx"},
        {"language": "xx"},
        {"radius": -10},
        {"webrtc": "bla"},
        {"webrtc": {}},
    ):
        with pytest.raises(MultipleInvalid):
            CORE_CONFIG_SCHEMA(value)

    CORE_CONFIG_SCHEMA(
        {
            "name": "Test name",
            "latitude": "-23.45",
            "longitude": "123.45",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "unit_system": "metric",
            "currency": "USD",
            "customize": {"sensor.temperature": {"hidden": True}},
            "country": "SE",
            "language": "sv",
            "radius": "10",
            "webrtc": {"ice_servers": [{"url": "stun:custom_stun_server:3478"}]},
        }
    )


def test_core_config_schema_internal_external_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we warn for internal/external URL with path."""
    CORE_CONFIG_SCHEMA(
        {
            "external_url": "https://www.example.com/bla",
            "internal_url": "http://example.local/yo",
        }
    )

    assert "Invalid external_url set" in caplog.text
    assert "Invalid internal_url set" in caplog.text


def test_customize_dict_schema() -> None:
    """Test basic customize config validation."""
    values = ({ATTR_FRIENDLY_NAME: None}, {ATTR_ASSUMED_STATE: "2"})

    for val in values:
        with pytest.raises(MultipleInvalid):
            _CUSTOMIZE_DICT_SCHEMA(val)

    assert _CUSTOMIZE_DICT_SCHEMA({ATTR_FRIENDLY_NAME: 2, ATTR_ASSUMED_STATE: "0"}) == {
        ATTR_FRIENDLY_NAME: "2",
        ATTR_ASSUMED_STATE: False,
    }


def test_webrtc_schema() -> None:
    """Test webrtc config validation."""
    invalid_webrtc_configs = (
        "bla",
        {},
        {"ice_servers": [], "unknown_key": 123},
        {"ice_servers": [{}]},
        {"ice_servers": [{"invalid_key": 123}]},
    )

    valid_webrtc_configs = (
        (
            {"ice_servers": []},
            {"ice_servers": []},
        ),
        (
            {"ice_servers": {"url": "stun:custom_stun_server:3478"}},
            {"ice_servers": [{"url": ["stun:custom_stun_server:3478"]}]},
        ),
        (
            {"ice_servers": [{"url": "stun:custom_stun_server:3478"}]},
            {"ice_servers": [{"url": ["stun:custom_stun_server:3478"]}]},
        ),
        (
            {"ice_servers": [{"url": ["stun:custom_stun_server:3478"]}]},
            {"ice_servers": [{"url": ["stun:custom_stun_server:3478"]}]},
        ),
        (
            {
                "ice_servers": [
                    {
                        "url": ["stun:custom_stun_server:3478"],
                        "username": "bla",
                        "credential": "hunter2",
                    }
                ]
            },
            {
                "ice_servers": [
                    {
                        "url": ["stun:custom_stun_server:3478"],
                        "username": "bla",
                        "credential": "hunter2",
                    }
                ]
            },
        ),
    )

    for config in invalid_webrtc_configs:
        with pytest.raises(MultipleInvalid):
            CORE_CONFIG_SCHEMA({"webrtc": config})

    for config, validated_webrtc in valid_webrtc_configs:
        validated = CORE_CONFIG_SCHEMA({"webrtc": config})
        assert validated["webrtc"] == validated_webrtc


def test_validate_stun_or_turn_url() -> None:
    """Test _validate_stun_or_turn_url."""
    invalid_urls = (
        "custom_stun_server",
        "custom_stun_server:3478",
        "bum:custom_stun_server:3478" "http://blah.com:80",
    )

    valid_urls = (
        "stun:custom_stun_server:3478",
        "turn:custom_stun_server:3478",
        "stuns:custom_stun_server:3478",
        "turns:custom_stun_server:3478",
        # The validator does not reject urls with path
        "stun:custom_stun_server:3478/path",
        "turn:custom_stun_server:3478/path",
        "stuns:custom_stun_server:3478/path",
        "turns:custom_stun_server:3478/path",
        # The validator allows any query
        "stun:custom_stun_server:3478?query",
        "turn:custom_stun_server:3478?query",
        "stuns:custom_stun_server:3478?query",
        "turns:custom_stun_server:3478?query",
    )

    for url in invalid_urls:
        with pytest.raises(Invalid):
            _validate_stun_or_turn_url(url)

    for url in valid_urls:
        assert _validate_stun_or_turn_url(url) == url


def test_customize_glob_is_ordered() -> None:
    """Test that customize_glob preserves order."""
    conf = CORE_CONFIG_SCHEMA({"customize_glob": OrderedDict()})
    assert isinstance(conf["customize_glob"], OrderedDict)


async def _compute_state(hass: HomeAssistant, config: dict[str, Any]) -> State | None:
    await async_process_ha_core_config(hass, config)

    entity = Entity()
    entity.entity_id = "test.test"
    entity.hass = hass
    entity.schedule_update_ha_state()

    await hass.async_block_till_done()

    return hass.states.get("test.test")


async def test_entity_customization(hass: HomeAssistant) -> None:
    """Test entity customization through configuration."""
    config = {
        CONF_LATITUDE: 50,
        CONF_LONGITUDE: 50,
        CONF_NAME: "Test",
        CONF_CUSTOMIZE: {"test.test": {"hidden": True}},
    }

    state = await _compute_state(hass, config)

    assert state.attributes["hidden"]


async def test_loading_configuration_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading core config onto hass object."""
    hass_storage["core.config"] = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "metric",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "currency": "EUR",
            "country": "SE",
            "language": "sv",
            "radius": 150,
        },
        "key": "core.config",
        "version": 1,
        "minor_version": 4,
    }
    await async_process_ha_core_config(hass, {"allowlist_external_dirs": "/etc"})

    assert hass.config.latitude == 55
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units is METRIC_SYSTEM
    assert hass.config.time_zone == "Europe/Copenhagen"
    assert hass.config.external_url == "https://www.example.com"
    assert hass.config.internal_url == "http://example.local"
    assert hass.config.currency == "EUR"
    assert hass.config.country == "SE"
    assert hass.config.language == "sv"
    assert hass.config.radius == 150
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert hass.config.config_source is ConfigSource.STORAGE


async def test_loading_configuration_from_storage_with_yaml_only(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading core and YAML config onto hass object."""
    hass_storage["core.config"] = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "metric",
        },
        "key": "core.config",
        "version": 1,
    }
    await async_process_ha_core_config(
        hass, {"media_dirs": {"mymedia": "/usr"}, "allowlist_external_dirs": "/etc"}
    )

    assert hass.config.latitude == 55
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units is METRIC_SYSTEM
    assert hass.config.time_zone == "Europe/Copenhagen"
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert hass.config.media_dirs == {"mymedia": "/usr"}
    assert hass.config.config_source is ConfigSource.STORAGE


async def test_migration_and_updating_configuration(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test updating configuration stores the new configuration."""
    core_data = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "imperial",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "currency": "BTC",
        },
        "key": "core.config",
        "version": 1,
        "minor_version": 1,
    }
    hass_storage["core.config"] = dict(core_data)
    await async_process_ha_core_config(hass, {"allowlist_external_dirs": "/etc"})
    await hass.config.async_update(latitude=50, currency="USD")

    expected_new_core_data = copy.deepcopy(core_data)
    # From async_update above
    expected_new_core_data["data"]["latitude"] = 50
    expected_new_core_data["data"]["currency"] = "USD"
    # 1.1 -> 1.2 store migration with migrated unit system
    expected_new_core_data["data"]["unit_system_v2"] = "us_customary"
    # 1.1 -> 1.3 defaults for country and language
    expected_new_core_data["data"]["country"] = None
    expected_new_core_data["data"]["language"] = "en"
    # 1.1 -> 1.4 defaults for zone radius
    expected_new_core_data["data"]["radius"] = 100
    # Bumped minor version
    expected_new_core_data["minor_version"] = 4
    assert hass_storage["core.config"] == expected_new_core_data
    assert hass.config.latitude == 50
    assert hass.config.currency == "USD"
    assert hass.config.country is None
    assert hass.config.language == "en"
    assert hass.config.radius == 100


async def test_override_stored_configuration(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading core and YAML config onto hass object."""
    hass_storage["core.config"] = {
        "data": {
            "elevation": 10,
            "latitude": 55,
            "location_name": "Home",
            "longitude": 13,
            "time_zone": "Europe/Copenhagen",
            "unit_system": "metric",
        },
        "key": "core.config",
        "version": 1,
    }
    await async_process_ha_core_config(
        hass, {"latitude": 60, "allowlist_external_dirs": "/etc"}
    )

    assert hass.config.latitude == 60
    assert hass.config.longitude == 13
    assert hass.config.elevation == 10
    assert hass.config.location_name == "Home"
    assert hass.config.units is METRIC_SYSTEM
    assert hass.config.time_zone == "Europe/Copenhagen"
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert hass.config.config_source is ConfigSource.YAML


async def test_loading_configuration(hass: HomeAssistant) -> None:
    """Test loading core config onto hass object."""
    await async_process_ha_core_config(
        hass,
        {
            "latitude": 60,
            "longitude": 50,
            "elevation": 25,
            "name": "Huis",
            "unit_system": "imperial",
            "time_zone": "America/New_York",
            "allowlist_external_dirs": "/etc",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "media_dirs": {"mymedia": "/usr"},
            "debug": True,
            "currency": "EUR",
            "country": "SE",
            "language": "sv",
            "radius": 150,
            "webrtc": {"ice_servers": [{"url": "stun:custom_stun_server:3478"}]},
        },
    )

    assert hass.config.latitude == 60
    assert hass.config.longitude == 50
    assert hass.config.elevation == 25
    assert hass.config.location_name == "Huis"
    assert hass.config.units is US_CUSTOMARY_SYSTEM
    assert hass.config.time_zone == "America/New_York"
    assert hass.config.external_url == "https://www.example.com"
    assert hass.config.internal_url == "http://example.local"
    assert len(hass.config.allowlist_external_dirs) == 3
    assert "/etc" in hass.config.allowlist_external_dirs
    assert "/usr" in hass.config.allowlist_external_dirs
    assert hass.config.media_dirs == {"mymedia": "/usr"}
    assert hass.config.config_source is ConfigSource.YAML
    assert hass.config.debug is True
    assert hass.config.currency == "EUR"
    assert hass.config.country == "SE"
    assert hass.config.language == "sv"
    assert hass.config.radius == 150
    assert hass.config.webrtc == webrtc_util.RTCConfiguration(
        [webrtc_util.RTCIceServer(urls=["stun:custom_stun_server:3478"])]
    )


@pytest.mark.parametrize(
    ("minor_version", "users", "user_data", "default_language"),
    [
        (2, (), {}, "en"),
        (2, ({"is_owner": True},), {}, "en"),
        (
            2,
            ({"id": "user1", "is_owner": True},),
            {"user1": {"language": {"language": "sv"}}},
            "sv",
        ),
        (
            2,
            ({"id": "user1", "is_owner": False},),
            {"user1": {"language": {"language": "sv"}}},
            "en",
        ),
        (3, (), {}, "en"),
        (3, ({"is_owner": True},), {}, "en"),
        (
            3,
            ({"id": "user1", "is_owner": True},),
            {"user1": {"language": {"language": "sv"}}},
            "en",
        ),
        (
            3,
            ({"id": "user1", "is_owner": False},),
            {"user1": {"language": {"language": "sv"}}},
            "en",
        ),
    ],
)
async def test_language_default(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    minor_version,
    users,
    user_data,
    default_language,
) -> None:
    """Test language config default to owner user's language during migration.

    This should only happen if the core store version < 1.3
    """
    core_data = {
        "data": {},
        "key": "core.config",
        "version": 1,
        "minor_version": minor_version,
    }
    hass_storage["core.config"] = dict(core_data)

    for user_config in users:
        user = MockUser(**user_config).add_to_hass(hass)
        if user.id not in user_data:
            continue
        storage_key = f"frontend.user_data_{user.id}"
        hass_storage[storage_key] = {
            "key": storage_key,
            "version": 1,
            "data": user_data[user.id],
        }

    await async_process_ha_core_config(
        hass,
        {},
    )
    assert hass.config.language == default_language


async def test_loading_configuration_default_media_dirs_docker(
    hass: HomeAssistant,
) -> None:
    """Test loading core config onto hass object."""
    with patch("homeassistant.core_config.is_docker_env", return_value=True):
        await async_process_ha_core_config(
            hass,
            {
                "name": "Huis",
            },
        )

    assert hass.config.location_name == "Huis"
    assert len(hass.config.allowlist_external_dirs) == 2
    assert "/media" in hass.config.allowlist_external_dirs
    assert hass.config.media_dirs == {"local": "/media"}


async def test_loading_configuration_from_packages(hass: HomeAssistant) -> None:
    """Test loading packages config onto hass object config."""
    await async_process_ha_core_config(
        hass,
        {
            "latitude": 39,
            "longitude": -1,
            "elevation": 500,
            "name": "Huis",
            "unit_system": "metric",
            "time_zone": "Europe/Madrid",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "packages": {
                "package_1": {"wake_on_lan": None},
                "package_2": {
                    "light": {"platform": "hue"},
                    "media_extractor": None,
                    "sun": None,
                },
            },
        },
    )

    # Empty packages not allowed
    with pytest.raises(MultipleInvalid):
        await async_process_ha_core_config(
            hass,
            {
                "latitude": 39,
                "longitude": -1,
                "elevation": 500,
                "name": "Huis",
                "unit_system": "metric",
                "time_zone": "Europe/Madrid",
                "packages": {"empty_package": None},
            },
        )


@pytest.mark.parametrize(
    ("unit_system_name", "expected_unit_system"),
    [
        ("metric", METRIC_SYSTEM),
        ("imperial", US_CUSTOMARY_SYSTEM),
        ("us_customary", US_CUSTOMARY_SYSTEM),
    ],
)
async def test_loading_configuration_unit_system(
    hass: HomeAssistant, unit_system_name: str, expected_unit_system: UnitSystem
) -> None:
    """Test backward compatibility when loading core config."""
    await async_process_ha_core_config(
        hass,
        {
            "latitude": 60,
            "longitude": 50,
            "elevation": 25,
            "name": "Huis",
            "unit_system": unit_system_name,
            "time_zone": "America/New_York",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
        },
    )

    assert hass.config.units is expected_unit_system


async def test_merge_customize(hass: HomeAssistant) -> None:
    """Test loading core config onto hass object."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        "unit_system": "imperial",
        "time_zone": "GMT",
        "customize": {"a.a": {"friendly_name": "A"}},
        "packages": {
            "pkg1": {"homeassistant": {"customize": {"b.b": {"friendly_name": "BB"}}}}
        },
    }
    await async_process_ha_core_config(hass, core_config)

    assert hass.data[DATA_CUSTOMIZE].get("b.b") == {"friendly_name": "BB"}


async def test_auth_provider_config(hass: HomeAssistant) -> None:
    """Test loading auth provider config onto hass object."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        "unit_system": "imperial",
        "time_zone": "GMT",
        CONF_AUTH_PROVIDERS: [
            {"type": "homeassistant"},
        ],
        CONF_AUTH_MFA_MODULES: [{"type": "totp"}, {"type": "totp", "id": "second"}],
    }
    if hasattr(hass, "auth"):
        del hass.auth
    await async_process_ha_core_config(hass, core_config)

    assert len(hass.auth.auth_providers) == 1
    assert hass.auth.auth_providers[0].type == "homeassistant"
    assert len(hass.auth.auth_mfa_modules) == 2
    assert hass.auth.auth_mfa_modules[0].id == "totp"
    assert hass.auth.auth_mfa_modules[1].id == "second"


async def test_auth_provider_config_default(hass: HomeAssistant) -> None:
    """Test loading default auth provider config."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        "unit_system": "imperial",
        "time_zone": "GMT",
    }
    if hasattr(hass, "auth"):
        del hass.auth
    await async_process_ha_core_config(hass, core_config)

    assert len(hass.auth.auth_providers) == 1
    assert hass.auth.auth_providers[0].type == "homeassistant"
    assert len(hass.auth.auth_mfa_modules) == 1
    assert hass.auth.auth_mfa_modules[0].id == "totp"


async def test_disallowed_auth_provider_config(hass: HomeAssistant) -> None:
    """Test loading insecure example auth provider is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        "unit_system": "imperial",
        "time_zone": "GMT",
        CONF_AUTH_PROVIDERS: [
            {
                "type": "insecure_example",
                "users": [
                    {
                        "username": "test-user",
                        "password": "test-pass",
                        "name": "Test Name",
                    }
                ],
            }
        ],
    }
    with pytest.raises(Invalid):
        await async_process_ha_core_config(hass, core_config)


async def test_disallowed_duplicated_auth_provider_config(hass: HomeAssistant) -> None:
    """Test loading insecure example auth provider is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        "unit_system": "imperial",
        "time_zone": "GMT",
        CONF_AUTH_PROVIDERS: [{"type": "homeassistant"}, {"type": "homeassistant"}],
    }
    with pytest.raises(Invalid):
        await async_process_ha_core_config(hass, core_config)


async def test_disallowed_auth_mfa_module_config(hass: HomeAssistant) -> None:
    """Test loading insecure example auth mfa module is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        "unit_system": "imperial",
        "time_zone": "GMT",
        CONF_AUTH_MFA_MODULES: [
            {
                "type": "insecure_example",
                "data": [{"user_id": "mock-user", "pin": "test-pin"}],
            }
        ],
    }
    with pytest.raises(Invalid):
        await async_process_ha_core_config(hass, core_config)


async def test_disallowed_duplicated_auth_mfa_module_config(
    hass: HomeAssistant,
) -> None:
    """Test loading insecure example auth mfa module is disallowed."""
    core_config = {
        "latitude": 60,
        "longitude": 50,
        "elevation": 25,
        "name": "Huis",
        "unit_system": "imperial",
        "time_zone": "GMT",
        CONF_AUTH_MFA_MODULES: [{"type": "totp"}, {"type": "totp"}],
    }
    with pytest.raises(Invalid):
        await async_process_ha_core_config(hass, core_config)


async def test_core_config_schema_historic_currency(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test core config schema."""
    await async_process_ha_core_config(hass, {"currency": "LTT"})

    issue = issue_registry.async_get_issue("homeassistant", "historic_currency")
    assert issue
    assert issue.translation_placeholders == {"currency": "LTT"}


async def test_core_store_historic_currency(
    hass: HomeAssistant, hass_storage: dict[str, Any], issue_registry: ir.IssueRegistry
) -> None:
    """Test core config store."""
    core_data = {
        "data": {
            "currency": "LTT",
        },
        "key": "core.config",
        "version": 1,
        "minor_version": 1,
    }
    hass_storage["core.config"] = dict(core_data)
    await async_process_ha_core_config(hass, {})

    issue_id = "historic_currency"
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert issue
    assert issue.translation_placeholders == {"currency": "LTT"}

    await hass.config.async_update(currency="EUR")
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert not issue


async def test_core_config_schema_no_country(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test core config schema."""
    await async_process_ha_core_config(hass, {})

    issue = issue_registry.async_get_issue("homeassistant", "country_not_configured")
    assert issue


async def test_core_store_no_country(
    hass: HomeAssistant, hass_storage: dict[str, Any], issue_registry: ir.IssueRegistry
) -> None:
    """Test core config store."""
    core_data = {
        "data": {},
        "key": "core.config",
        "version": 1,
        "minor_version": 1,
    }
    hass_storage["core.config"] = dict(core_data)
    await async_process_ha_core_config(hass, {})

    issue_id = "country_not_configured"
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert issue

    await hass.config.async_update(country="SE")
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert not issue


async def test_configuration_legacy_template_is_removed(hass: HomeAssistant) -> None:
    """Test loading core config onto hass object."""
    await async_process_ha_core_config(
        hass,
        {
            "latitude": 60,
            "longitude": 50,
            "elevation": 25,
            "name": "Huis",
            "unit_system": "imperial",
            "time_zone": "America/New_York",
            "allowlist_external_dirs": "/etc",
            "external_url": "https://www.example.com",
            "internal_url": "http://example.local",
            "media_dirs": {"mymedia": "/usr"},
            "legacy_templates": True,
            "debug": True,
            "currency": "EUR",
            "country": "SE",
            "language": "sv",
            "radius": 150,
        },
    )

    assert not getattr(hass.config, "legacy_templates")
