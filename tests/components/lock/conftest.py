"""Fixtures for the lock entity platform tests."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.lock import LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.setup import async_setup_component

from tests.testing_config.custom_components.test.lock import MockLock


@pytest.fixture
async def default_code() -> str | UndefinedType:
    """Return the default code for the test lock entity."""
    return UNDEFINED


@pytest.fixture
async def code_format() -> str | None:
    """Return the default code for the test lock entity."""
    return None


@pytest.fixture(name="supported_features")
async def lock_supported_features() -> LockEntityFeature:
    """Return the supported features for the test lock entity."""
    return LockEntityFeature.OPEN


@pytest.fixture(name="mock_lock")
async def setup_lock_platform_test_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
    default_code: str | None | UndefinedType,
    code_format: str | None,
    supported_features: LockEntityFeature,
) -> MockLock:
    """Set up lock entity using an entity platform."""

    await hass.async_block_till_done()

    platform = getattr(hass.components, "test.lock")
    platform.init(empty=True)

    # Pre-register entities
    entry = entity_registry.async_get_or_create("lock", "test", "lock")
    if not isinstance(default_code, UndefinedType):
        entity_registry.async_update_entity_options(
            entry.entity_id,
            "lock",
            {
                "default_code": default_code,
            },
        )
    platform.ENTITIES["lock1"] = platform.MockLock(
        code_format=code_format,
        supported_features=supported_features,
        unique_id="lock",
        calls_open=MagicMock(),
        calls_lock=MagicMock(),
        calls_unlock=MagicMock(),
    )

    assert await async_setup_component(hass, "lock", {"lock": {"platform": "test"}})
    await hass.async_block_till_done()

    entity0: MockLock = platform.ENTITIES["lock1"]
    return entity0
