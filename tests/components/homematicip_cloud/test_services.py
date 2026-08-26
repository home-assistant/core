"""Tests for HomematicIP Cloud services."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.homematicip_cloud import DOMAIN
from homeassistant.components.homematicip_cloud.services import (
    ATTR_PIN,
    SERVICE_PULL_LATCH,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .helper import HomeFactory


@pytest.mark.parametrize(
    ("service_data", "expected_pin"),
    [({ATTR_PIN: "1234"}, "1234"), ({}, None)],
)
async def test_pull_latch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    default_mock_hap_factory: HomeFactory,
    full_flush_lock_controller_device_data: dict[str, Any],
    service_data: dict[str, str],
    expected_pin: str | None,
) -> None:
    """The pull_latch service forwards the PIN a button press cannot carry."""
    entity_id = "button.universal_motorschloss_controller_door_opener"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universal Motorschloss Controller"],
        extra_devices=[full_flush_lock_controller_device_data],
    )

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry

    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    auth_channel = next(
        ch
        for ch in hmip_device.functionalChannels
        if ch.functionalChannelType.name == "ACCESS_AUTHORIZATION_CHANNEL"
        and ch.channelRole == "DOOR_OPENER_ACTUATOR"
    )

    with patch.object(
        auth_channel, "async_pull_latch", new_callable=AsyncMock
    ) as mock_pull_latch:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PULL_LATCH,
            {ATTR_DEVICE_ID: entity_entry.device_id} | service_data,
            blocking=True,
        )

    mock_pull_latch.assert_awaited_once_with(expected_pin)


async def test_pull_latch_on_non_opener_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Targeting a device that is not a door opener reports a clear error."""
    await default_mock_hap_factory.async_get_mock_hap(test_devices=["Garagentor"])

    entity_entry = entity_registry.async_get("button.garagentor")
    assert entity_entry

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PULL_LATCH,
            {ATTR_DEVICE_ID: entity_entry.device_id},
            blocking=True,
        )


async def test_pull_latch_unknown_device(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Targeting an unknown device reports a clear error."""
    await default_mock_hap_factory.async_get_mock_hap(test_devices=["Garagentor"])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PULL_LATCH,
            {ATTR_DEVICE_ID: "does-not-exist"},
            blocking=True,
        )
