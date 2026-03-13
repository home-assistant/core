"""Test the Google Assistant filter."""
import pytest
from unittest.mock import MagicMock

from homeassistant.components.google_assistant import const, http
from homeassistant.components.google_assistant.const import (
    CONF_FILTER,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITY_GLOBS,
    CONF_EXCLUDE_ENTITY_GLOBS,
    CONF_ENTITY_CONFIG,
    CONF_EXPOSE,
    CONF_EXPOSED_DOMAINS,
)
from homeassistant.helpers import entityfilter

# Minimal valid config for GoogleConfig init
MINIMAL_CONFIG = {
    const.CONF_PROJECT_ID: "project_id",
    const.CONF_SERVICE_ACCOUNT: {
        const.CONF_PRIVATE_KEY: "private_key",
        const.CONF_CLIENT_EMAIL: "email",
    },
    const.CONF_REPORT_STATE: True,
}

@pytest.fixture
def mock_config(hass):
    """Create a mock config."""
    def _create_config(filter_config=None, entity_config=None, exposed_domains=None):
        config_data = MINIMAL_CONFIG.copy()
        if filter_config:
            config_data[CONF_FILTER] = filter_config
        if entity_config:
            config_data[CONF_ENTITY_CONFIG] = entity_config
        if exposed_domains:
            config_data[CONF_EXPOSED_DOMAINS] = exposed_domains
        
        # Initialize GoogleConfig
        config = http.GoogleConfig(hass, config_data)
        if filter_config:
            # Manually initialize the filter as we are mocking
            # Normally this happens in __init__ but since we pass data in config...
            # Actually, GoogleConfig __init__ handles it now.
            pass
        return config
    
    return _create_config

def test_filter_include_domains(hass, mock_config):
    """Test that the filter include domains works."""
    config = mock_config(filter_config={
        CONF_INCLUDE_DOMAINS: ["light"]
    })

    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("switch.kitchen", "on")

    assert config.should_expose(hass.states.get("light.kitchen"))
    assert not config.should_expose(hass.states.get("switch.kitchen"))

def test_filter_include_entities(hass, mock_config):
    """Test that the filter include entities works."""
    config = mock_config(filter_config={
        CONF_INCLUDE_ENTITIES: ["light.kitchen"]
    })

    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.living_room", "on")

    assert config.should_expose(hass.states.get("light.kitchen"))
    assert not config.should_expose(hass.states.get("light.living_room"))

def test_filter_include_globs(hass, mock_config):
    """Test that the filter include globs works."""
    config = mock_config(filter_config={
        CONF_INCLUDE_ENTITY_GLOBS: ["light.kitchen_*"]
    })

    hass.states.async_set("light.kitchen_ceiling", "on")
    hass.states.async_set("light.kitchen_counter", "on")
    hass.states.async_set("light.living_room", "on")

    assert config.should_expose(hass.states.get("light.kitchen_ceiling"))
    assert config.should_expose(hass.states.get("light.kitchen_counter"))
    assert not config.should_expose(hass.states.get("light.living_room"))

def test_filter_exclude_globs(hass, mock_config):
    """Test that the filter exclude globs works."""
    config = mock_config(filter_config={
        CONF_INCLUDE_DOMAINS: ["light"],
        CONF_EXCLUDE_ENTITY_GLOBS: ["*bedroom*"]
    })

    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.master_bedroom", "on")

    assert config.should_expose(hass.states.get("light.kitchen"))
    assert not config.should_expose(hass.states.get("light.master_bedroom"))

def test_filter_legacy_fallback(hass, mock_config):
    """Test that we fall back to exposed_domains if no filter configured."""
    config = mock_config(exposed_domains=["light"])

    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("switch.kitchen", "on")

    assert config.should_expose(hass.states.get("light.kitchen"))
    assert not config.should_expose(hass.states.get("switch.kitchen"))

def test_explicit_expose_overrides_filter(hass, mock_config):
    """Test that entity config expose overrides filter."""
    config = mock_config(
        filter_config={CONF_INCLUDE_DOMAINS: ["light"]},
        entity_config={
            "switch.exposed": {CONF_EXPOSE: True},
            "light.hidden": {CONF_EXPOSE: False}
        }
    )

    hass.states.async_set("switch.exposed", "on")
    hass.states.async_set("light.normal", "on")
    hass.states.async_set("light.hidden", "on")

    assert config.should_expose(hass.states.get("switch.exposed"))
    assert config.should_expose(hass.states.get("light.normal"))
    assert not config.should_expose(hass.states.get("light.hidden"))
