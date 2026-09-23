"""Tests for the Marketplace pre-release switches."""

from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.setup import async_setup_component

from . import CategoryTestData, category_test_data_parametrized, get_marketplace
from .const import REPOSITORY_INTEGRATION_ID


@pytest.fixture(autouse=True)
async def python_script_integration(hass: HomeAssistant, config_dir: Path) -> None:
    """Load the python script integration so its category is active."""
    (config_dir / "python_scripts").mkdir()
    assert await async_setup_component(hass, "python_script", {})


async def _reload(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> MarketplaceManager:
    """Reload the config entry and return the Marketplace object that replaced it."""
    await hass.config_entries.async_reload(
        marketplace.configuration.config_entry.entry_id
    )
    await hass.async_block_till_done()
    return get_marketplace(hass)


@pytest.fixture
async def switch_entity(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    entity_registry: er.EntityRegistry,
) -> str:
    """Return the enabled pre-release switch of a downloaded integration."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True
    repository.data.installed_version = "1.0.0"

    await _reload(hass, marketplace)

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, REPOSITORY_INTEGRATION_ID
    )
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    await _reload(hass, get_marketplace(hass))

    return entity_id


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_switch_entity(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    entity_registry: er.EntityRegistry,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the pre-release switch of every repository category."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    repository.data.installed = True
    repository.data.installed_version = category_test_data["version_base"]

    await _reload(hass, marketplace)

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, category_test_data["id"]
    )
    assert entity_id is not None

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")


async def test_switch_is_disabled_by_default(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a repository without pre-releases hides the switch."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True

    await _reload(hass, marketplace)

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, REPOSITORY_INTEGRATION_ID
    )

    assert (
        entity_registry.async_get(entity_id).disabled_by
        is RegistryEntryDisabler.INTEGRATION
    )
    assert hass.states.get(entity_id) is None


async def test_switch_is_enabled_for_a_pre_release(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a repository already on pre-releases shows the switch."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True
    repository.data.show_beta = True

    await _reload(hass, marketplace)

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, REPOSITORY_INTEGRATION_ID
    )

    assert entity_registry.async_get(entity_id).disabled_by is None
    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch_turn_on_and_off(hass: HomeAssistant, switch_entity: str) -> None:
    """Test opting a repository in to and out of pre-releases."""
    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert hass.states.get(switch_entity).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: switch_entity},
        blocking=True,
    )

    assert repository.data.show_beta is True
    assert hass.states.get(switch_entity).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: switch_entity},
        blocking=True,
    )

    assert repository.data.show_beta is False
    assert hass.states.get(switch_entity).state == STATE_OFF


async def test_switch_keeps_the_last_fetched_time(
    hass: HomeAssistant, switch_entity: str
) -> None:
    """Test that toggling the switch does not lose the last fetch time."""
    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    last_fetched = repository.data.last_fetched

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: switch_entity},
        blocking=True,
    )

    assert repository.data.last_fetched == last_fetched


async def test_switch_becomes_unavailable(
    hass: HomeAssistant, switch_entity: str
) -> None:
    """Test that removing a repository makes its switch unavailable."""
    marketplace = get_marketplace(hass)
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = False
    repository.data.last_fetched = None
    marketplace.coordinators[repository.data.category].async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(switch_entity).state == "unavailable"
