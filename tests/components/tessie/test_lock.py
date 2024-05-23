"""Test the Tessie lock platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.lock import (
    ATTR_CODE,
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import async_get as async_get_issue_registry

from .common import DOMAIN, assert_entities, setup_platform


async def test_locks(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the lock entity is correct."""

    # Create the deprecated speed limit lock entity
    entity_registry.async_get_or_create(
        LOCK_DOMAIN,
        DOMAIN,
        "VINVINVIN-vehicle_state_speed_limit_mode_active",
        original_name="Charge cable lock",
        has_entity_name=True,
        translation_key="vehicle_state_speed_limit_mode_active",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    entry = await setup_platform(hass, [Platform.LOCK])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    # Test lock set value functions
    entity_id = "lock.test_lock"
    with patch("homeassistant.components.tessie.lock.lock") as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_run.assert_called_once()
    assert hass.states.get(entity_id).state == STATE_LOCKED

    with patch("homeassistant.components.tessie.lock.unlock") as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_run.assert_called_once()
    assert hass.states.get(entity_id).state == STATE_UNLOCKED

    # Test charge cable lock set value functions
    entity_id = "lock.test_charge_cable_lock"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )

    with patch(
        "homeassistant.components.tessie.lock.open_unlock_charge_port"
    ) as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        assert hass.states.get(entity_id).state == STATE_UNLOCKED
        mock_run.assert_called_once()


async def test_speed_limit_lock(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the deprecated speed limit lock entity is correct."""

    issue_registry = async_get_issue_registry(hass)

    # Create the deprecated speed limit lock entity
    entity = entity_registry.async_get_or_create(
        LOCK_DOMAIN,
        DOMAIN,
        "VINVINVIN-vehicle_state_speed_limit_mode_active",
        original_name="Charge cable lock",
        has_entity_name=True,
        translation_key="vehicle_state_speed_limit_mode_active",
    )

    with patch(
        "homeassistant.components.tessie.lock.automations_with_entity",
        return_value=["item"],
    ):
        await setup_platform(hass, [Platform.LOCK])
        assert issue_registry.async_get_issue(
            DOMAIN, f"deprecated_speed_limit_{entity.entity_id}_item"
        )

    # Test lock set value functions
    with patch(
        "homeassistant.components.tessie.lock.enable_speed_limit"
    ) as mock_enable_speed_limit:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: [entity.entity_id], ATTR_CODE: "1234"},
            blocking=True,
        )
        assert hass.states.get(entity.entity_id).state == STATE_LOCKED
        mock_enable_speed_limit.assert_called_once()
        # Assert issue has been raised in the issue register
        assert issue_registry.async_get_issue(DOMAIN, "deprecated_speed_limit_locked")

    with patch(
        "homeassistant.components.tessie.lock.disable_speed_limit"
    ) as mock_disable_speed_limit:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: [entity.entity_id], ATTR_CODE: "1234"},
            blocking=True,
        )
        assert hass.states.get(entity.entity_id).state == STATE_UNLOCKED
        mock_disable_speed_limit.assert_called_once()
        assert issue_registry.async_get_issue(DOMAIN, "deprecated_speed_limit_unlocked")

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: [entity.entity_id], ATTR_CODE: "abc"},
            blocking=True,
        )
