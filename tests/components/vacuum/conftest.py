"""Fixtures for Vacuum platform tests."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MockVacuum

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(name="supported_features")
async def alarm_control_panel_supported_features() -> VacuumEntityFeature:
    """Return the supported features for the test alarm control panel entity."""
    return (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.MAP
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )


@pytest.fixture(name="mock_vacuum_entity")
async def setup_vacuum_platform_test_entity(
    hass: HomeAssistant,
    config_flow_fixture: None,
    entity_registry: er.EntityRegistry,
    supported_features: VacuumEntityFeature,
) -> MagicMock:
    """Set up alarm control panel entity using an entity platform."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [VACUUM_DOMAIN]
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed sensor without device class -> no name
    entity = MockVacuum(
        supported_features=supported_features,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test vacuum platform via config entry."""
        async_add_entities([entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{VACUUM_DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None

    return entity
