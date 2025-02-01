"""Fixtures for the lock entity platform tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    LockEntity,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockLock(LockEntity):
    """Mocked lock entity."""

    def __init__(
        self,
        supported_features: LockEntityFeature = LockEntityFeature(0),
        code_format: str | None = None,
    ) -> None:
        """Initialize the lock."""
        self.calls_open = MagicMock()
        self.calls_lock = MagicMock()
        self.calls_unlock = MagicMock()
        self._attr_code_format = code_format
        self._attr_supported_features = supported_features
        self._attr_has_entity_name = True
        self._attr_name = "test_lock"
        self._attr_unique_id = "very_unique_lock_id"
        super().__init__()

    def lock(self, **kwargs: Any) -> None:
        """Mock lock lock calls."""
        self.calls_lock(**kwargs)

    def unlock(self, **kwargs: Any) -> None:
        """Mock lock unlock calls."""
        self.calls_unlock(**kwargs)

    def open(self, **kwargs: Any) -> None:
        """Mock lock open calls."""
        self.calls_open(**kwargs)


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture
async def code_format() -> str | None:
    """Return the code format for the test lock entity."""
    return None


@pytest.fixture(name="supported_features")
async def lock_supported_features() -> LockEntityFeature:
    """Return the supported features for the test lock entity."""
    return LockEntityFeature.OPEN


@pytest.fixture(name="mock_lock_entity")
async def setup_lock_platform_test_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    code_format: str | None,
    supported_features: LockEntityFeature,
) -> MagicMock:
    """Set up lock entity using an entity platform."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [LOCK_DOMAIN]
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
    entity = MockLock(
        supported_features=supported_features,
        code_format=code_format,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test lock platform via config entry."""
        async_add_entities([entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{LOCK_DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None

    return entity
