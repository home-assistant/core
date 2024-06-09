"""Tests for the Monzo component."""

from unittest.mock import AsyncMock

import pytest
from pytest_unordered import unordered

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.monzo.const import (
    DOMAIN,
    EVENT_TRANSACTION_CREATED,
    MONZO_EVENT,
)
from homeassistant.components.monzo.device_trigger import (
    ACCOUNT_ID,
    async_validate_trigger_config,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import TEST_ACCOUNTS, TEST_POTS

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture
def automation_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track automation calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


def _make_trigger(account_id: str, device_id: str):
    return {
        CONF_PLATFORM: CONF_DEVICE,
        ACCOUNT_ID: account_id,
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device_id,
        CONF_TYPE: EVENT_TRANSACTION_CREATED,
        "metadata": {},
    }


async def test_trigger_setup(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all triggers set up for all devices."""
    await setup_integration(hass, polling_config_entry)

    for account in TEST_ACCOUNTS:
        device = device_registry.async_get_device(identifiers={(DOMAIN, account["id"])})

        expected_triggers = [_make_trigger(account["id"], device.id)]

        triggers = [
            trigger
            for trigger in await async_get_device_automations(
                hass, DeviceAutomationType.TRIGGER, device.id
            )
            if trigger[CONF_DOMAIN] == DOMAIN
        ]

        assert triggers == unordered(expected_triggers)


async def test_transaction_created_triggers_automation(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    automation_calls: list[ServiceCall],
) -> None:
    """Test triggering an automation with transaction_created event."""
    await setup_integration(hass, polling_config_entry)

    account = TEST_ACCOUNTS[0]
    test_amount = 123

    device = device_registry.async_get_device(identifiers={(DOMAIN, account["id"])})

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "trigger": _make_trigger(account["id"], device.id),
                    "action": {
                        "service": "test.automation",
                        "data": {"amount": "{{ trigger.event.data.data.amount }}"},
                    },
                },
            ]
        },
    )

    assert len(hass.states.async_entity_ids(AUTOMATION_DOMAIN)) == 1

    event_data = {
        CONF_TYPE: EVENT_TRANSACTION_CREATED,
        "data": {"amount": test_amount},
        ACCOUNT_ID: account["id"],
    }

    hass.bus.async_fire(
        event_type=MONZO_EVENT,
        event_data=event_data,
    )
    await hass.async_block_till_done()

    assert len(automation_calls) == 1
    assert automation_calls[0].data["amount"] == test_amount


async def test_trigger_validation_fails_if_not_valid_device(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test trigger validation fails if not valid device."""
    await setup_integration(hass, polling_config_entry)

    account = TEST_ACCOUNTS[0]

    trigger = _make_trigger(account["id"], "invalid_device_id")

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_validate_trigger_config(hass, trigger)


async def test_trigger_validation_fails_if_pot(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test trigger validation fails if given device is a pot."""
    await setup_integration(hass, polling_config_entry)

    pot = TEST_POTS[0]

    device = device_registry.async_get_device(identifiers={(DOMAIN, pot["id"])})

    trigger = _make_trigger(pot["id"], device.id)

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_validate_trigger_config(hass, trigger)
