"""Tests for the Monzo component."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from monzopy import InvalidMonzoAPIResponseError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.monzo.const import (
    DEVICE_MODEL_ACCOUNT,
    DEVICE_MODEL_POT,
    DOMAIN,
)
from homeassistant.components.monzo.sensor import (
    ACCOUNT_SENSORS,
    POT_SENSORS,
    MonzoSensorEntityDescription,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)

from . import setup_integration
from .conftest import TEST_ACCOUNTS, TEST_POTS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator

EXPECTED_VALUE_GETTERS = {
    "balance": lambda x: x["balance"]["balance"] / 100,
    "total_balance": lambda x: x["balance"]["total_balance"] / 100,
    "spend_today": lambda x: abs(x["balance"]["spend_today"]) / 100,
    "pot_balance": lambda x: x["balance"] / 100,
}


async def async_get_entity_id(
    hass: HomeAssistant,
    acc_id: str,
    description: MonzoSensorEntityDescription,
) -> str | None:
    """Get an entity id for a user's attribute."""
    entity_registry = er.async_get(hass)
    unique_id = f"{acc_id}_{description.key}"

    return entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)


def async_assert_state_equals(
    entity_id: str,
    state_obj: State,
    expected: Any,
    description: MonzoSensorEntityDescription,
) -> None:
    """Assert at given state matches what is expected."""
    assert state_obj, f"Expected entity {entity_id} to exist but it did not"

    assert state_obj.state == str(expected), (
        f"Expected {expected} but was {state_obj.state} "
        f"for measure {description.name}, {entity_id}"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_default_enabled_entities(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities enabled by default."""
    await setup_integration(hass, polling_config_entry)

    for acc in TEST_ACCOUNTS:
        for sensor_description in ACCOUNT_SENSORS:
            entity_id = await async_get_entity_id(hass, acc["id"], sensor_description)
            assert entity_id
            assert entity_registry.async_is_registered(entity_id)

            state = hass.states.get(entity_id)
            assert state.state == str(
                EXPECTED_VALUE_GETTERS[sensor_description.key](acc)
            )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unavailable_entity(
    hass: HomeAssistant,
    basic_monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities enabled by default."""
    await setup_integration(hass, polling_config_entry)
    basic_monzo.user_account.pots.return_value = [{"id": "pot_savings"}]
    freezer.tick(timedelta(minutes=100))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    entity_id = await async_get_entity_id(hass, TEST_POTS[0]["id"], POT_SENSORS[0])
    state = hass.states.get(entity_id)
    assert state.state == "unknown"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_deleted_pot_is_removed_and_can_be_rediscovered(
    hass: HomeAssistant,
    basic_monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a deleted pot is removed without affecting another pot."""
    holiday_pot = {
        "id": "pot_holiday",
        "name": "Holiday",
        "balance": 12345,
        "currency": "EUR",
    }
    basic_monzo.user_account.pots.return_value = [TEST_POTS[0], holiday_pot]
    await setup_integration(hass, polling_config_entry)

    deleted_entity_id = await async_get_entity_id(
        hass, TEST_POTS[0]["id"], POT_SENSORS[0]
    )
    holiday_entity_id = await async_get_entity_id(
        hass, holiday_pot["id"], POT_SENSORS[0]
    )
    assert deleted_entity_id
    assert holiday_entity_id
    label = label_registry.async_create("Savings")
    deleted_entity_id = entity_registry.async_update_entity(
        deleted_entity_id,
        labels={label.label_id},
        name="Rainy day fund",
        new_entity_id="sensor.rainy_day_fund",
    ).entity_id
    await hass.async_block_till_done()

    basic_monzo.user_account.pots.return_value = [{**holiday_pot, "balance": 54321}]
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(deleted_entity_id) is None
    assert entity_registry.async_get(deleted_entity_id) is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, TEST_POTS[0]["id"]), polling_config_entry.entry_id
        )
        is None
    )
    assert hass.states.get(holiday_entity_id).state == "543.21"

    basic_monzo.user_account.pots.return_value = [TEST_POTS[0], holiday_pot]
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    restored_entity_id = await async_get_entity_id(
        hass, TEST_POTS[0]["id"], POT_SENSORS[0]
    )
    assert restored_entity_id == deleted_entity_id
    restored_state = hass.states.get(restored_entity_id)
    assert restored_state is not None
    assert restored_state.state == "1345.78"
    restored_entry = entity_registry.async_get(restored_entity_id)
    assert restored_entry is not None
    assert restored_entry.labels == {label.label_id}
    assert restored_entry.name == "Rainy day fund"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "monzo")
async def test_stale_resource_is_removed_during_initial_refresh(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a resource removed while Home Assistant was stopped is cleaned up."""
    polling_config_entry.add_to_hass(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=polling_config_entry.entry_id,
        identifiers={(DOMAIN, "pot_deleted")},
        name="Deleted pot",
    )
    stale_entity = entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id="pot_deleted_pot_balance",
        config_entry=polling_config_entry,
        device_id=stale_device.id,
    )

    assert await hass.config_entries.async_setup(polling_config_entry.entry_id)

    assert device_registry.async_get(stale_device.id) is None
    assert entity_registry.async_get(stale_entity.entity_id) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_new_accounts_and_pots_are_discovered(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors are added for accounts and pots discovered after setup."""
    await setup_integration(hass, polling_config_entry)
    new_account = {
        "id": "acc_joint",
        "name": "Joint Account",
        "type": "uk_retail_joint",
        "balance": {"balance": 456, "total_balance": 654, "currency": "GBP"},
        "owners": [
            {"preferred_name": "Jake Martin"},
            {"preferred_name": "Jane Martin"},
        ],
    }
    new_pot = {
        "id": "pot_holiday",
        "name": "Holiday",
        "balance": 12345,
        "currency": "EUR",
    }
    monzo.user_account.accounts.return_value = [*TEST_ACCOUNTS, new_account]
    monzo.user_account.pots.return_value = [*TEST_POTS, new_pot]

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    account_entity_id = await async_get_entity_id(
        hass, new_account["id"], ACCOUNT_SENSORS[0]
    )
    pot_entity_id = await async_get_entity_id(hass, new_pot["id"], POT_SENSORS[0])
    assert account_entity_id is not None
    account_state = hass.states.get(account_entity_id)
    assert account_state is not None
    assert account_state.state == "4.56"
    assert pot_entity_id is not None
    pot_state = hass.states.get(pot_entity_id)
    assert pot_state is not None
    assert pot_state.state == "123.45"
    account_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, new_account["id"]), polling_config_entry.entry_id
    )
    pot_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, new_pot["id"]), polling_config_entry.entry_id
    )
    assert account_device is not None
    assert account_device.name == "Joint Account — Jake Martin & Jane Martin"
    assert account_device.model == DEVICE_MODEL_ACCOUNT
    assert pot_device is not None
    assert pot_device.name == "Holiday"
    assert pot_device.model == DEVICE_MODEL_POT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.monzo.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, polling_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, polling_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("api_error", "expected_log_messages"),
    [
        pytest.param(
            InvalidMonzoAPIResponseError(),
            ("The Monzo API returned an invalid response",),
            id="invalid-response",
        ),
        pytest.param(
            InvalidMonzoAPIResponseError({"acc_id": None}, "account_id"),
            (
                "The Monzo API returned an invalid response. Enable debug logging for details",
                "account_id",
                "acc_id",
            ),
            id="missing-key",
        ),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    api_error: InvalidMonzoAPIResponseError,
    expected_log_messages: tuple[str, ...],
) -> None:
    """Test an invalid API response makes entities unavailable."""
    await setup_integration(hass, polling_config_entry)

    monzo.user_account.accounts.side_effect = api_error
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for message in expected_log_messages:
        assert message in caplog.text

    entity_id = await async_get_entity_id(
        hass, TEST_ACCOUNTS[0]["id"], ACCOUNT_SENSORS[0]
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
