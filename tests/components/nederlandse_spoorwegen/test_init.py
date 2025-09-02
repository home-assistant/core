"""Test the Nederlandse Spoorwegen init module."""

from unittest.mock import patch

from homeassistant.components.nederlandse_spoorwegen import async_setup
from homeassistant.components.nederlandse_spoorwegen.const import CONF_ROUTES, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity

from tests.common import MockConfigEntry


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
        options={},
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nederlandse_spoorwegen.coordinator.NSDataUpdateCoordinator.async_config_entry_first_refresh"
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_coordinator_failure(hass: HomeAssistant) -> None:
    """Test setup failure due to coordinator error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
        options={},
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nederlandse_spoorwegen.coordinator.NSDataUpdateCoordinator.async_config_entry_first_refresh",
        side_effect=Exception("API error"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry_success(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
        options={},
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nederlandse_spoorwegen.coordinator.NSDataUpdateCoordinator.async_config_entry_first_refresh"
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_failure(hass: HomeAssistant) -> None:
    """Test unload failure."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
        options={},
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nederlandse_spoorwegen.coordinator.NSDataUpdateCoordinator.async_config_entry_first_refresh"
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(config_entry.entry_id)


async def test_async_setup_platform_migration(hass: HomeAssistant) -> None:
    """Test automatic migration of platform-based configuration."""
    config = {
        "sensor": [
            {
                "platform": DOMAIN,
                CONF_API_KEY: "test_api_key",
                "routes": [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
            }
        ]
    }

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow:
        result = await async_setup(hass, config)

    assert result is True
    mock_flow.assert_called_once_with(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_API_KEY: "test_api_key",
            "routes": [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
        },
    )


async def test_async_setup_integration_migration(hass: HomeAssistant) -> None:
    """Test automatic migration of integration-level configuration."""
    config = {
        DOMAIN: {
            CONF_API_KEY: "test_api_key",
            "routes": [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
        }
    }

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow:
        result = await async_setup(hass, config)

    assert result is True
    mock_flow.assert_called_once_with(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_API_KEY: "test_api_key",
            "routes": [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
        },
    )


async def test_async_setup_no_config(hass: HomeAssistant) -> None:
    """Test setup with no YAML configuration."""
    config = {}

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow:
        result = await async_setup(hass, config)

    assert result is True
    mock_flow.assert_not_called()


async def test_async_setup_yaml_with_existing_config_entry(hass: HomeAssistant) -> None:
    """Test that repair issue is created when YAML config exists even with existing config entry."""
    # Create an existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "existing_api_key"},
        options={CONF_ROUTES: []},
    )
    existing_entry.add_to_hass(hass)

    config = {
        DOMAIN: {
            CONF_API_KEY: "test_api_key",
            "routes": [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
        }
    }

    with (
        patch.object(hass.config_entries.flow, "async_init") as mock_flow,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.async_create_issue"
        ) as mock_create_issue,
    ):
        result = await async_setup(hass, config)

    assert result is True

    # Import flow should NOT be called since config entry already exists
    mock_flow.assert_not_called()

    # But repair issue should still be created to notify user about YAML config
    mock_create_issue.assert_called_once_with(
        hass,
        DOMAIN,
        "integration_yaml_migration",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="integration_yaml_migration",
    )


async def test_async_setup_platform_yaml_with_existing_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test that repair issue is created when platform YAML config exists even with existing config entry."""
    # Create an existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "existing_api_key"},
        options={CONF_ROUTES: []},
    )
    existing_entry.add_to_hass(hass)

    config = {
        "sensor": [
            {
                "platform": DOMAIN,
                CONF_API_KEY: "test_api_key",
                CONF_ROUTES: [{"name": "Test Route", "from": "Asd", "to": "Rtd"}],
            }
        ]
    }

    with (
        patch.object(hass.config_entries.flow, "async_init") as mock_flow,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.async_create_issue"
        ) as mock_create_issue,
    ):
        result = await async_setup(hass, config)

    assert result is True

    # Import flow should NOT be called since config entry already exists
    mock_flow.assert_not_called()

    # But repair issue should still be created to notify user about YAML config
    mock_create_issue.assert_called_once_with(
        hass,
        DOMAIN,
        "platform_yaml_migration",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="platform_yaml_migration",
    )
