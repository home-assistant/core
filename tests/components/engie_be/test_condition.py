"""Test the ENGIE Belgium conditions."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from aioengiebelgium import EnergyContractsResponse
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components import automation
from homeassistant.components.engie_be.condition import (
    EpexHourPriceIsNegativeCondition,
    EpexHourPriceMeetsThresholdCondition,
)
from homeassistant.components.engie_be.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    BAN,
    BAN_2,
    BRUSSELS_TIME_ZONE,
    automation_calls,
    build_contracts,
    build_epex_payload_with_negative_current,
    build_relations,
    household_device_id,
    setup_dynamic_entry,
    setup_entry,
)


def _brussels(hour: int, minute: int) -> datetime:
    """Return a Brussels moment on the frozen Saturday."""
    return datetime(2026, 10, 3, hour, minute, tzinfo=BRUSSELS_TIME_ZONE)


async def _async_condition_passes(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    condition_key: str,
    options: dict[str, Any],
) -> bool:
    """Run an automation gated by one ENGIE Belgium condition."""
    hass.states.async_set("input_boolean.test", STATE_OFF)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "trigger": "state",
                    "entity_id": "input_boolean.test",
                    "to": STATE_ON,
                },
                "condition": {
                    "condition": f"{DOMAIN}.{condition_key}",
                    "options": options,
                },
                "action": {"action": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("input_boolean.test", STATE_ON)
    await hass.async_block_till_done()
    return len(automation_calls(service_calls)) == 1


@pytest.mark.parametrize(
    ("condition_key", "minute", "expected"),
    [
        pytest.param("epex_hour_price_is_negative", 0, True, id="hour_negative"),
        pytest.param("epex_hour_price_is_negative", 30, True, id="hour_still"),
        pytest.param(
            "epex_quarter_hour_price_is_negative", 0, True, id="quarter_negative"
        ),
        pytest.param(
            "epex_quarter_hour_price_is_negative", 30, False, id="quarter_positive"
        ),
    ],
)
async def test_negative_condition(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    condition_key: str,
    minute: int,
    expected: bool,
) -> None:
    """Test the negative conditions follow the price of their granularity."""
    freezer.move_to(_brussels(14, minute))
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_with_negative_current
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)

    assert (
        await _async_condition_passes(
            hass, service_calls, condition_key, {"device_id": device_id}
        )
        is expected
    )


@pytest.mark.parametrize(
    ("condition_key", "options", "expected"),
    [
        pytest.param(
            "epex_hour_price_meets_threshold", {"above": 0.14}, True, id="above"
        ),
        pytest.param(
            "epex_hour_price_meets_threshold", {"below": 0.14}, False, id="not_below"
        ),
        pytest.param(
            "epex_quarter_hour_price_meets_threshold",
            {"above": 0.155, "below": 0.16},
            True,
            id="range",
        ),
        pytest.param(
            "epex_quarter_hour_price_meets_threshold",
            {"above": 0.16},
            False,
            id="not_above",
        ),
    ],
)
async def test_threshold_condition(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    condition_key: str,
    options: dict[str, float],
    expected: bool,
) -> None:
    """Test the threshold conditions compare the current price with the range."""
    freezer.move_to(_brussels(14, 45))
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)

    assert (
        await _async_condition_passes(
            hass, service_calls, condition_key, {"device_id": device_id, **options}
        )
        is expected
    )


@pytest.mark.parametrize(
    ("ban", "expected"),
    [
        pytest.param(BAN, True, id="dynamic"),
        pytest.param(BAN_2, False, id="fixed"),
    ],
)
@pytest.mark.usefixtures("frozen_afternoon")
async def test_condition_per_household_tariff(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    ban: str,
    expected: bool,
) -> None:
    """Test the conditions only pass for a household with a dynamic tariff."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )

    def _contracts(queried_ban: str) -> EnergyContractsResponse:
        return build_contracts(dynamic=queried_ban == BAN)

    mock_engie_client.return_value.async_get_energy_contracts.side_effect = _contracts
    await setup_entry(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, ban), mock_config_entry.entry_id
    )
    assert device is not None

    assert (
        await _async_condition_passes(
            hass,
            service_calls,
            "epex_hour_price_meets_threshold",
            {"device_id": device.id, "above": -1},
        )
        is expected
    )


@pytest.mark.usefixtures("frozen_afternoon")
async def test_condition_without_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test the EPEX prices stay fresh for a condition when no entity listens."""
    with patch("homeassistant.components.engie_be._PLATFORMS", []):
        await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
        device_id = household_device_id(device_registry, mock_config_entry)

        freezer.move_to(datetime(2026, 10, 5, 14, 0, tzinfo=BRUSSELS_TIME_ZONE))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert await _async_condition_passes(
            hass,
            service_calls,
            "epex_hour_price_meets_threshold",
            {"device_id": device_id, "above": -1},
        )


@pytest.mark.usefixtures("frozen_afternoon")
async def test_condition_without_dynamic_tariff(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test the conditions fail for a household with a fixed tariff."""
    await setup_entry(hass, mock_config_entry)
    device_id = household_device_id(device_registry, mock_config_entry)

    assert not await _async_condition_passes(
        hass,
        service_calls,
        "epex_hour_price_meets_threshold",
        {"device_id": device_id, "above": -1},
    )


@pytest.mark.parametrize(
    "device_id_of",
    [
        pytest.param(lambda other_device: "missing", id="missing"),
        pytest.param(lambda other_device: other_device.id, id="other_integration"),
    ],
)
async def test_condition_invalid_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device_id_of: Callable[[dr.DeviceEntry], str],
) -> None:
    """Test the conditions only accept ENGIE Belgium devices."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "device")}
    )
    device_id = device_id_of(other_device)

    with pytest.raises(probatio.Invalid, match="is not an ENGIE Belgium device"):
        await EpexHourPriceIsNegativeCondition.async_validate_complete_config(
            hass,
            {
                "condition": f"{DOMAIN}.epex_hour_price_is_negative",
                "options": {"device_id": device_id},
            },
        )


async def test_condition_invalid_threshold(hass: HomeAssistant) -> None:
    """Test the threshold conditions require at least one bound."""
    with pytest.raises(probatio.Invalid, match="Set above, below or both"):
        await EpexHourPriceMeetsThresholdCondition.async_validate_complete_config(
            hass,
            {
                "condition": f"{DOMAIN}.epex_hour_price_meets_threshold",
                "options": {"device_id": "device"},
            },
        )
