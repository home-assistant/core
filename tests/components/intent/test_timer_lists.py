"""Tests for intent timers kept in timer list entities."""

from collections.abc import Generator, Iterable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from homeassistant.components.intent import (
    DOMAIN,
    TimerEventType,
    TimerInfo,
    async_device_supports_timers,
    async_register_timer_handler,
)
from homeassistant.components.intent.timers import (
    TIMER_DATA,
    MultipleTimersMatchedError,
    TimerManager,
    TimerNotFoundError,
)
from homeassistant.components.timer_list import (
    InMemoryTimerListEntity,
    TimerListEntity,
    TimerStatus,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component

TEST_DOMAIN = "test"
KITCHEN = "kitchen"
LIVING_ROOM = "living_room"
BEDROOM = "bedroom"


class DeviceTimerList(InMemoryTimerListEntity):
    """Timer list of a test device."""

    _attr_has_entity_name = True
    _attr_name = "Timers"

    def __init__(self, device: str) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._attr_unique_id = f"{device}-timers"
        self._attr_device_info = DeviceInfo(
            identifiers={(TEST_DOMAIN, device)}, name=device
        )


@dataclass
class TimerDevice:
    """A test device and its timer list."""

    device_id: str
    timer_list: TimerListEntity


class MockFlow(ConfigFlow):
    """Config flow of the test integration."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock the config flow of the test integration."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def _async_setup_timer_lists(
    hass: HomeAssistant, timer_lists: Iterable[TimerListEntity]
) -> None:
    """Set up a test integration providing timer lists."""

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.TIMER_LIST]
        )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        async_add_entities(timer_lists)

    mock_integration(hass, MockModule(TEST_DOMAIN, async_setup_entry=async_setup_entry))
    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{Platform.TIMER_LIST}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )
    entry = MockConfigEntry(domain=TEST_DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def init_components(hass: HomeAssistant) -> None:
    """Initialize required components for tests."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, DOMAIN, {})


@pytest.fixture
async def devices(
    hass: HomeAssistant,
    init_components: None,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> dict[str, TimerDevice]:
    """Set up kitchen and living room devices with a timer list each.

    The kitchen and living room are on the first floor.
    """
    timer_lists = {
        KITCHEN: DeviceTimerList(KITCHEN),
        LIVING_ROOM: DeviceTimerList(LIVING_ROOM),
    }
    await _async_setup_timer_lists(hass, timer_lists.values())

    floor = floor_registry.async_create("First floor")
    devices: dict[str, TimerDevice] = {}
    for name, timer_list in timer_lists.items():
        area = area_registry.async_create(
            name.replace("_", " "), floor_id=floor.floor_id
        )
        entity_entry = entity_registry.async_get(timer_list.entity_id)
        assert entity_entry is not None
        assert entity_entry.device_id is not None
        device_registry.async_update_device(entity_entry.device_id, area_id=area.id)
        devices[name] = TimerDevice(entity_entry.device_id, timer_list)

    return devices


async def _handle(
    hass: HomeAssistant,
    intent_type: str,
    device_id: str | None,
    **slots: Any,
) -> intent.IntentResponse:
    """Handle a timer intent from a device."""
    return await intent.async_handle(
        hass,
        "test",
        intent_type,
        {name: {"value": value} for name, value in slots.items()},
        device_id=device_id,
    )


async def _create_timer(
    timer_device: TimerDevice, *, minutes: int = 5, name: str | None = None
) -> str:
    """Create a timer directly on a device's timer list."""
    return await timer_device.timer_list.async_create_timer(
        name=name, duration=timedelta(minutes=minutes)
    )


def _statuses(timer_device: TimerDevice) -> list[TimerStatus]:
    """Return the status of each timer on a device."""
    return [timer.status for timer in timer_device.timer_list.timers]


async def test_start_timer(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test a timer is created on the timer list of the requesting device."""
    kitchen = devices[KITCHEN]

    result = await _handle(
        hass,
        intent.INTENT_START_TIMER,
        kitchen.device_id,
        name="pizza",
        minutes=1,
        seconds=30,
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    timers = kitchen.timer_list.timers
    assert len(timers) == 1
    assert timers[0].name == "pizza"
    assert timers[0].created_duration == timedelta(seconds=90)
    assert devices[LIVING_ROOM].timer_list.timers == []
    assert not hass.data[TIMER_DATA].timers


async def test_delayed_command_uses_timer_manager(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test a delayed command is not added to the device's timer list."""
    kitchen = devices[KITCHEN]

    result = await _handle(
        hass,
        intent.INTENT_START_TIMER,
        kitchen.device_id,
        minutes=5,
        conversation_command="what time is it",
    )

    assert result.response_type is intent.IntentResponseType.ACTION_DONE
    assert kitchen.timer_list.timers == []
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    assert [timer.device_id for timer in timer_manager.timers.values()] == [
        kitchen.device_id
    ]


async def test_timer_list_preferred_over_handler(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test a device with a timer list does not use its timer handler."""
    kitchen = devices[KITCHEN]
    events: list[TimerEventType] = []

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        events.append(event_type)

    async_register_timer_handler(hass, kitchen.device_id, handle_timer)

    await _handle(hass, intent.INTENT_START_TIMER, kitchen.device_id, minutes=5)

    assert events == []
    assert len(kitchen.timer_list.timers) == 1
    assert not hass.data[TIMER_DATA].timers


async def test_cancel_timer(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test cancelling the only timer, from another device."""
    kitchen = devices[KITCHEN]
    await _create_timer(kitchen)

    await _handle(hass, intent.INTENT_CANCEL_TIMER, devices[LIVING_ROOM].device_id)

    assert _statuses(kitchen) == [TimerStatus.CANCELLED]


@pytest.mark.parametrize(
    ("slots", "expected_kitchen", "expected_living_room"),
    [
        pytest.param(
            {"area": "Kitchen"},
            [TimerStatus.CANCELLED],
            [TimerStatus.ACTIVE],
            id="area",
        ),
        pytest.param(
            {"start_minutes": 5},
            [TimerStatus.CANCELLED],
            [TimerStatus.ACTIVE],
            id="start_time",
        ),
        pytest.param(
            {"start_seconds": 600},
            [TimerStatus.ACTIVE],
            [TimerStatus.CANCELLED],
            id="start_time_in_other_units",
        ),
        pytest.param(
            {"name": "Pizza"},
            [TimerStatus.CANCELLED],
            [TimerStatus.ACTIVE],
            id="name",
        ),
    ],
)
async def test_cancel_timer_on_other_device(
    hass: HomeAssistant,
    devices: dict[str, TimerDevice],
    slots: dict[str, Any],
    expected_kitchen: list[TimerStatus],
    expected_living_room: list[TimerStatus],
) -> None:
    """Test a timer on any device can be cancelled by area, start time or name."""
    await _create_timer(devices[KITCHEN], minutes=5, name="pizza")
    await _create_timer(devices[LIVING_ROOM], minutes=10)

    await _handle(hass, intent.INTENT_CANCEL_TIMER, None, **slots)

    assert _statuses(devices[KITCHEN]) == expected_kitchen
    assert _statuses(devices[LIVING_ROOM]) == expected_living_room


@pytest.mark.parametrize("requesting_device", [KITCHEN, LIVING_ROOM])
async def test_requesting_device_disambiguates(
    hass: HomeAssistant, devices: dict[str, TimerDevice], requesting_device: str
) -> None:
    """Test the requesting device's own timer wins when several match."""
    await _create_timer(devices[KITCHEN])
    await _create_timer(devices[LIVING_ROOM])

    await _handle(
        hass,
        intent.INTENT_CANCEL_TIMER,
        devices[requesting_device].device_id,
        start_minutes=5,
    )

    for name, timer_device in devices.items():
        expected = (
            TimerStatus.CANCELLED if name == requesting_device else TimerStatus.ACTIVE
        )
        assert _statuses(timer_device) == [expected]


async def test_area_disambiguates(
    hass: HomeAssistant,
    devices: dict[str, TimerDevice],
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test a timer in the requesting device's area wins when several match."""
    kitchen_area = area_registry.async_get_area_by_name("kitchen")
    assert kitchen_area is not None
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    satellite = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "satellite")}
    )
    device_registry.async_update_device(satellite.id, area_id=kitchen_area.id)
    await _create_timer(devices[KITCHEN])
    await _create_timer(devices[LIVING_ROOM])

    await _handle(hass, intent.INTENT_CANCEL_TIMER, satellite.id)

    assert _statuses(devices[KITCHEN]) == [TimerStatus.CANCELLED]
    assert _statuses(devices[LIVING_ROOM]) == [TimerStatus.ACTIVE]


async def test_floor_disambiguates(
    hass: HomeAssistant,
    devices: dict[str, TimerDevice],
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test a timer on the requesting device's floor wins when several match."""
    other_floor = floor_registry.async_create("Second floor")
    bedroom_area = area_registry.async_create(BEDROOM, floor_id=other_floor.floor_id)
    device_registry.async_update_device(
        devices[LIVING_ROOM].device_id, area_id=bedroom_area.id
    )
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    satellite = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("other", "satellite")}
    )
    hallway = area_registry.async_create(
        "hallway",
        floor_id=floor_registry.async_get_floor_by_name("First floor").floor_id,
    )
    device_registry.async_update_device(satellite.id, area_id=hallway.id)
    await _create_timer(devices[KITCHEN])
    await _create_timer(devices[LIVING_ROOM])

    await _handle(hass, intent.INTENT_CANCEL_TIMER, satellite.id)

    assert _statuses(devices[KITCHEN]) == [TimerStatus.CANCELLED]
    assert _statuses(devices[LIVING_ROOM]) == [TimerStatus.ACTIVE]


async def test_entity_area_overrides_device_area(
    hass: HomeAssistant,
    devices: dict[str, TimerDevice],
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test the timer list's own area is used over its device's area."""
    bedroom_area = area_registry.async_create(BEDROOM)
    entity_registry.async_update_entity(
        devices[LIVING_ROOM].timer_list.entity_id, area_id=bedroom_area.id
    )
    await _create_timer(devices[KITCHEN])
    await _create_timer(devices[LIVING_ROOM])

    await _handle(hass, intent.INTENT_CANCEL_TIMER, None, area=BEDROOM)

    assert _statuses(devices[KITCHEN]) == [TimerStatus.ACTIVE]
    assert _statuses(devices[LIVING_ROOM]) == [TimerStatus.CANCELLED]


async def test_multiple_timers_matched(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test an error when several timers match and nothing tells them apart."""
    await _create_timer(devices[KITCHEN])
    await _create_timer(devices[LIVING_ROOM])

    with pytest.raises(MultipleTimersMatchedError):
        await _handle(hass, intent.INTENT_CANCEL_TIMER, None)


async def test_timer_not_found(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test finished and cancelled timers are not matched."""
    kitchen = devices[KITCHEN]
    timer_id = await _create_timer(kitchen)
    await kitchen.timer_list.async_cancel_timer(timer_id)

    with pytest.raises(TimerNotFoundError):
        await _handle(hass, intent.INTENT_CANCEL_TIMER, kitchen.device_id)


async def test_cancel_all_timers(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test cancelling the timers of every device and of the timer manager."""
    legacy_events: list[TimerEventType] = []

    @callback
    def handle_timer(event_type: TimerEventType, timer: TimerInfo) -> None:
        legacy_events.append(event_type)

    async_register_timer_handler(hass, "legacy_device", handle_timer)
    await _handle(hass, intent.INTENT_START_TIMER, "legacy_device", minutes=5)
    await _create_timer(devices[KITCHEN])
    await _create_timer(devices[LIVING_ROOM])

    result = await _handle(hass, intent.INTENT_CANCEL_ALL_TIMERS, None)

    assert result.speech_slots == {"canceled": 3}
    assert _statuses(devices[KITCHEN]) == [TimerStatus.CANCELLED]
    assert _statuses(devices[LIVING_ROOM]) == [TimerStatus.CANCELLED]
    assert legacy_events == [TimerEventType.STARTED, TimerEventType.CANCELLED]


async def test_cancel_all_timers_in_area(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test cancelling all timers of an area."""
    await _create_timer(devices[KITCHEN], minutes=5)
    await _create_timer(devices[KITCHEN], minutes=10)
    await _create_timer(devices[LIVING_ROOM])

    result = await _handle(hass, intent.INTENT_CANCEL_ALL_TIMERS, None, area="kitchen")

    assert result.speech_slots == {"canceled": 2, "area": "kitchen"}
    assert _statuses(devices[KITCHEN]) == [TimerStatus.CANCELLED] * 2
    assert _statuses(devices[LIVING_ROOM]) == [TimerStatus.ACTIVE]


@pytest.mark.usefixtures("freezer")
@pytest.mark.parametrize(
    ("intent_type", "seconds", "expected_remaining"),
    [
        pytest.param(intent.INTENT_INCREASE_TIMER, 30, 330, id="increase"),
        pytest.param(intent.INTENT_DECREASE_TIMER, 30, 270, id="decrease"),
    ],
)
async def test_change_timer(
    hass: HomeAssistant,
    devices: dict[str, TimerDevice],
    intent_type: str,
    seconds: int,
    expected_remaining: int,
) -> None:
    """Test adding and removing time on a timer list timer."""
    kitchen = devices[KITCHEN]
    await _create_timer(kitchen)

    await _handle(hass, intent_type, kitchen.device_id, seconds=seconds)

    timer = kitchen.timer_list.timers[0]
    assert timer.status == TimerStatus.ACTIVE
    assert timer.finishes_at is not None
    assert timer.finishes_at - timer.created_at == timedelta(seconds=expected_remaining)


async def test_pause_unpause_timer(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test pausing and resuming a timer list timer."""
    kitchen = devices[KITCHEN]
    await _create_timer(kitchen)

    await _handle(hass, intent.INTENT_PAUSE_TIMER, kitchen.device_id)
    assert _statuses(kitchen) == [TimerStatus.PAUSED]

    await _handle(hass, intent.INTENT_UNPAUSE_TIMER, kitchen.device_id)
    assert _statuses(kitchen) == [TimerStatus.ACTIVE]


async def test_timer_status(
    hass: HomeAssistant,
    devices: dict[str, TimerDevice],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reporting the status of timer list timers, own device first."""
    kitchen = devices[KITCHEN]
    living_room = devices[LIVING_ROOM]
    living_room_id = await _create_timer(living_room, minutes=90, name="roast")
    kitchen_id = await _create_timer(kitchen, minutes=5)
    await kitchen.timer_list.async_pause_timer(kitchen_id)
    freezer.tick(timedelta(minutes=2, seconds=5))

    result = await _handle(hass, intent.INTENT_TIMER_STATUS, kitchen.device_id)

    assert result.speech_slots == {
        "timers": [
            {
                "id": kitchen_id,
                "name": "",
                "device_id": kitchen.device_id,
                "language": "en",
                "start_hours": 0,
                "start_minutes": 5,
                "start_seconds": 0,
                "is_active": False,
                "hours_left": 0,
                "minutes_left": 5,
                "seconds_left": 0,
                "rounded_hours_left": 0,
                "rounded_minutes_left": 5,
                "rounded_seconds_left": 0,
                "total_seconds_left": 300,
            },
            {
                "id": living_room_id,
                "name": "roast",
                "device_id": living_room.device_id,
                "language": "en",
                "start_hours": 1,
                "start_minutes": 30,
                "start_seconds": 0,
                "is_active": True,
                "hours_left": 1,
                "minutes_left": 27,
                "seconds_left": 55,
                "rounded_hours_left": 1,
                "rounded_minutes_left": 30,
                "rounded_seconds_left": 0,
                "total_seconds_left": 5275,
            },
        ]
    }


@pytest.mark.usefixtures("init_components")
async def test_timer_list_without_device(hass: HomeAssistant) -> None:
    """Test timers of a timer list that has no device are matched by name."""
    timer_list = InMemoryTimerListEntity()
    timer_list.entity_id = "timer_list.oven"
    await _async_setup_timer_lists(hass, [timer_list])
    await timer_list.async_create_timer(name="oven", duration=timedelta(minutes=20))

    await _handle(hass, intent.INTENT_CANCEL_TIMER, None, name="oven")

    assert [timer.status for timer in timer_list.timers] == [TimerStatus.CANCELLED]


async def test_device_supports_timers(
    hass: HomeAssistant, devices: dict[str, TimerDevice]
) -> None:
    """Test a device with a timer list supports timers."""
    assert async_device_supports_timers(hass, devices[KITCHEN].device_id)
    assert not async_device_supports_timers(hass, "other_device")
