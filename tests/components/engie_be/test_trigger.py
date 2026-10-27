"""Test the ENGIE Belgium triggers."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from aioengiebelgium import EngieBeCommunicationError
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from homeassistant.components import automation
from homeassistant.components.automation import ATTR_SOURCE, EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.engie_be.const import DOMAIN, EPEX_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    BAN,
    BRUSSELS_TIME_ZONE,
    automation_calls,
    build_contracts,
    build_epex_payload,
    build_epex_payload_with_gap,
    build_epex_payload_with_negative_current,
    build_epex_payload_without_tomorrow,
    household_device_id,
    setup_dynamic_entry,
    setup_entry,
)


def _brussels(day: int, hour: int, minute: int) -> datetime:
    """Return a Brussels moment in October 2026."""
    return datetime(2026, 10, day, hour, minute, tzinfo=BRUSSELS_TIME_ZONE)


async def _async_setup_trigger_automation(
    hass: HomeAssistant, trigger_key: str, options: dict[str, Any]
) -> None:
    """Set up an automation with one ENGIE Belgium trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"trigger": f"{DOMAIN}.{trigger_key}", "options": options},
                "action": {
                    "action": "test.automation",
                    "data": {
                        "device_id": "{{ trigger.device_id }}",
                        "price": "{{ trigger.price | default(none) }}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()


async def _async_move_to(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, moment: datetime
) -> None:
    """Move the clock to the moment and let the quarter-hour tick run."""
    freezer.move_to(moment)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _async_count_calls_along(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
    moments: list[datetime],
) -> list[int]:
    """Return the number of automation calls after each moment."""
    counts = []
    for moment in moments:
        await _async_move_to(hass, freezer, moment)
        counts.append(len(automation_calls(service_calls)))
    return counts


_NEGATIVE_MOMENTS = [
    _brussels(3, 14, 0),
    _brussels(3, 14, 15),
    _brussels(3, 15, 0),
]


@pytest.mark.parametrize(
    ("trigger_key", "expected_counts", "expected_price", "expected_source"),
    [
        pytest.param(
            "epex_hour_price_became_negative",
            [1, 1, 1],
            -0.05,
            "hourly EPEX price became negative",
            id="hour_became",
        ),
        pytest.param(
            "epex_hour_price_no_longer_negative",
            [0, 0, 1],
            0.16,
            "hourly EPEX price no longer negative",
            id="hour_no_longer",
        ),
        pytest.param(
            "epex_quarter_hour_price_became_negative",
            [1, 1, 1],
            -0.05,
            "quarter-hourly EPEX price became negative",
            id="quarter_hour_became",
        ),
        pytest.param(
            "epex_quarter_hour_price_no_longer_negative",
            [0, 1, 1],
            0.1525,
            "quarter-hourly EPEX price no longer negative",
            id="quarter_hour_no_longer",
        ),
    ],
)
async def test_negative_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    trigger_key: str,
    expected_counts: list[int],
    expected_price: float,
    expected_source: str,
) -> None:
    """Test the negative price triggers fire on their own edge and granularity."""
    freezer.move_to(_brussels(3, 13, 45))
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_with_negative_current
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(hass, trigger_key, {"device_id": device_id})
    events = async_capture_events(hass, EVENT_AUTOMATION_TRIGGERED)

    assert (
        await _async_count_calls_along(hass, freezer, service_calls, _NEGATIVE_MOMENTS)
        == expected_counts
    )
    assert automation_calls(service_calls)[0].data == {
        "device_id": device_id,
        "price": pytest.approx(expected_price),
    }
    assert events[0].data[ATTR_SOURCE] == (
        f"{expected_source} for Main street 1, 1000 Brussels"
    )


_THRESHOLD_MOMENTS = [
    _brussels(3, 14, 15),
    _brussels(3, 14, 30),
    _brussels(3, 14, 45),
    _brussels(3, 15, 0),
    _brussels(3, 15, 15),
]


@pytest.mark.parametrize(
    ("trigger_key", "options", "expected_counts", "expected_price"),
    [
        pytest.param(
            "epex_current_hour_crossed_threshold",
            {"above": 0.155},
            [0, 0, 0, 1, 1],
            0.16,
            id="current_hour",
        ),
        pytest.param(
            "epex_next_hour_crossed_threshold",
            {"above": 0.165},
            [0, 0, 0, 1, 1],
            0.17,
            id="next_hour",
        ),
        pytest.param(
            "epex_current_quarter_hour_crossed_threshold",
            {"above": 0.156},
            [0, 0, 1, 1, 1],
            0.1575,
            id="current_quarter_hour",
        ),
        pytest.param(
            "epex_next_quarter_hour_crossed_threshold",
            {"above": 0.156},
            [0, 1, 1, 1, 1],
            0.1575,
            id="next_quarter_hour",
        ),
        pytest.param(
            "epex_current_quarter_hour_crossed_threshold",
            {"above": 0.151, "below": 0.156},
            [1, 1, 1, 1, 1],
            0.1525,
            id="range",
        ),
    ],
)
@pytest.mark.usefixtures("frozen_afternoon")
async def test_crossed_threshold_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    trigger_key: str,
    options: dict[str, float],
    expected_counts: list[int],
    expected_price: float,
) -> None:
    """Test the threshold triggers fire once when their price enters the range."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass, trigger_key, {"device_id": device_id, **options}
    )

    assert (
        await _async_count_calls_along(hass, freezer, service_calls, _THRESHOLD_MOMENTS)
        == expected_counts
    )
    assert automation_calls(service_calls)[0].data == {
        "device_id": device_id,
        "price": pytest.approx(expected_price),
    }


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tomorrow_prices_published_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger fires when the prices of tomorrow become available."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_without_tomorrow
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass, "epex_tomorrow_prices_published", {"device_id": device_id}
    )
    events = async_capture_events(hass, EVENT_AUTOMATION_TRIGGERED)

    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload
    )
    freezer.tick(EPEX_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(automation_calls(service_calls)) == 1
    assert automation_calls(service_calls)[0].data == {
        "device_id": device_id,
        "price": None,
    }
    assert events[0].data[ATTR_SOURCE] == (
        "EPEX prices for tomorrow published for Main street 1, 1000 Brussels"
    )


@pytest.mark.usefixtures("frozen_afternoon")
async def test_trigger_before_entry_loaded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test a trigger attached before the entry loads compares from the load on."""
    await _async_move_to(hass, freezer, _brussels(3, 14, 30))
    mock_engie_client.return_value.async_get_energy_contracts.return_value = (
        build_contracts(dynamic=True)
    )
    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, BAN)}
    )
    await _async_setup_trigger_automation(
        hass,
        "epex_current_quarter_hour_crossed_threshold",
        {"device_id": device.id, "above": 0.156},
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await _async_count_calls_along(
        hass, freezer, service_calls, [_brussels(3, 14, 45)]
    ) == [1]


@pytest.mark.usefixtures("frozen_afternoon")
async def test_trigger_without_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger fires when no entity listens to the EPEX prices."""
    client = mock_engie_client.return_value
    client.async_get_epex_prices.side_effect = build_epex_payload_without_tomorrow
    with patch("homeassistant.components.engie_be._PLATFORMS", []):
        await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
        device_id = household_device_id(device_registry, mock_config_entry)
        await _async_setup_trigger_automation(
            hass, "epex_tomorrow_prices_published", {"device_id": device_id}
        )

        client.async_get_epex_prices.side_effect = build_epex_payload
        await _async_move_to(hass, freezer, dt_util.utcnow() + EPEX_SCAN_INTERVAL)

        assert len(automation_calls(service_calls)) == 1


@pytest.mark.usefixtures("frozen_afternoon")
async def test_epex_polling_stops_after_unload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test the EPEX prices stop polling once the entry unloads."""
    client = mock_engie_client.return_value
    client.async_get_epex_prices.side_effect = build_epex_payload_without_tomorrow
    with patch("homeassistant.components.engie_be._PLATFORMS", []):
        await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        polls = client.async_get_epex_prices.call_count

        await _async_move_to(hass, freezer, dt_util.utcnow() + 2 * EPEX_SCAN_INTERVAL)

        assert client.async_get_epex_prices.call_count == polls


@pytest.mark.usefixtures("frozen_afternoon")
async def test_trigger_detached(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger stops listening when the automation is turned off."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass,
        "epex_current_quarter_hour_crossed_threshold",
        {"device_id": device_id, "above": 0.156},
    )

    await hass.services.async_call(
        automation.DOMAIN, "turn_off", {"entity_id": "all"}, blocking=True
    )

    assert await _async_count_calls_along(
        hass, freezer, service_calls, _THRESHOLD_MOMENTS
    ) == [0] * len(_THRESHOLD_MOMENTS)


@pytest.mark.usefixtures("frozen_afternoon")
async def test_trigger_after_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test a reload starts over, and the trigger keeps working after it."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass,
        "epex_current_quarter_hour_crossed_threshold",
        {"device_id": device_id, "above": 0.156},
    )

    await _async_move_to(hass, freezer, _brussels(3, 14, 30))
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await _async_count_calls_along(
        hass, freezer, service_calls, [_brussels(3, 14, 45)]
    ) == [1]


@pytest.mark.parametrize(
    ("side_effect", "expected_counts"),
    [
        pytest.param(build_epex_payload_with_negative_current, [1], id="fetched"),
        pytest.param(EngieBeCommunicationError("boom"), [0], id="fetch_failed"),
    ],
)
async def test_trigger_after_failed_fetch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    side_effect: Callable[..., Any] | Exception,
    expected_counts: list[int],
) -> None:
    """Test the trigger does not fire while the EPEX fetch fails."""
    freezer.move_to(_brussels(3, 13, 45))
    mock_engie_client.return_value.async_get_epex_prices.side_effect = side_effect
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass, "epex_hour_price_became_negative", {"device_id": device_id}
    )

    assert (
        await _async_count_calls_along(
            hass, freezer, service_calls, [_brussels(3, 14, 0)]
        )
        == expected_counts
    )


@pytest.mark.parametrize(
    ("trigger_key", "options"),
    [
        pytest.param("epex_hour_price_became_negative", {}, id="negative"),
        pytest.param(
            "epex_current_hour_crossed_threshold", {"above": 0.14}, id="threshold"
        ),
    ],
)
async def test_trigger_skips_missing_price(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    trigger_key: str,
    options: dict[str, float],
) -> None:
    """Test a missing hourly price is never compared against."""
    freezer.move_to(_brussels(3, 13, 45))
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_with_gap
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass, trigger_key, {"device_id": device_id, **options}
    )

    assert await _async_count_calls_along(
        hass, freezer, service_calls, [_brussels(3, 14, 0), _brussels(3, 15, 0)]
    ) == [0, 0]


@pytest.mark.usefixtures("frozen_afternoon")
async def test_trigger_without_dynamic_tariff(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger never fires for a household with a fixed tariff."""
    await setup_entry(hass, mock_config_entry)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass,
        "epex_current_quarter_hour_crossed_threshold",
        {"device_id": device_id, "above": 0.156},
    )

    assert await _async_count_calls_along(
        hass, freezer, service_calls, _THRESHOLD_MOMENTS
    ) == [0] * len(_THRESHOLD_MOMENTS)


@pytest.mark.usefixtures("frozen_afternoon")
async def test_trigger_device_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test a device removed while the automation was off is skipped."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    device_id = household_device_id(device_registry, mock_config_entry)
    await _async_setup_trigger_automation(
        hass,
        "epex_current_quarter_hour_crossed_threshold",
        {"device_id": device_id, "above": 0.156},
    )

    await hass.services.async_call(
        automation.DOMAIN, "turn_off", {"entity_id": "all"}, blocking=True
    )
    device_registry.async_remove_device(device_id)
    await hass.services.async_call(
        automation.DOMAIN, "turn_on", {"entity_id": "all"}, blocking=True
    )

    assert await _async_count_calls_along(
        hass, freezer, service_calls, _THRESHOLD_MOMENTS
    ) == [0] * len(_THRESHOLD_MOMENTS)


@pytest.mark.parametrize(
    "device_id_of",
    [
        pytest.param(lambda other_device: "missing", id="missing"),
        pytest.param(lambda other_device: other_device.id, id="other_integration"),
    ],
)
async def test_trigger_invalid_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device_id_of: Callable[[dr.DeviceEntry], str],
) -> None:
    """Test the triggers only accept ENGIE Belgium devices."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "device")}
    )
    device_id = device_id_of(other_device)

    with pytest.raises(probatio.Invalid, match="is not an ENGIE Belgium device"):
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": f"{DOMAIN}.epex_hour_price_became_negative",
                    "options": {"device_id": device_id},
                }
            ],
        )


@pytest.mark.parametrize(
    ("options", "message"),
    [
        pytest.param({}, "Set above, below or both", id="no_bounds"),
        pytest.param(
            {"above": 0.2, "below": 0.1}, "Above must be lower than below", id="empty"
        ),
        pytest.param({"above": 6}, "value must be at most 5", id="too_high"),
        pytest.param({"below": -2}, "value must be at least -1", id="too_low"),
    ],
)
async def test_trigger_invalid_threshold(
    hass: HomeAssistant, options: dict[str, float], message: str
) -> None:
    """Test the threshold triggers reject a range that can never match."""
    with pytest.raises(probatio.Invalid, match=message):
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": f"{DOMAIN}.epex_current_hour_crossed_threshold",
                    "options": {"device_id": "device", **options},
                }
            ],
        )
