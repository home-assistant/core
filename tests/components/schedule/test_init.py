"""Test for the Schedule integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.schedule import STORAGE_VERSION, STORAGE_VERSION_MINOR
from homeassistant.components.schedule.const import (
    ATTR_NEXT_EVENT,
    CONF_FRIDAY,
    CONF_FROM,
    CONF_MONDAY,
    CONF_SATURDAY,
    CONF_SUNDAY,
    CONF_THURSDAY,
    CONF_TO,
    CONF_TUESDAY,
    CONF_WEDNESDAY,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_NAME,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import EVENT_STATE_CHANGED, Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockUser, async_capture_events, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.fixture
def schedule_setup(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> Callable[..., Coroutine[Any, Any, bool]]:
    """Schedule setup."""

    async def _schedule_setup(
        items: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> bool:
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": STORAGE_VERSION,
                "minor_version": STORAGE_VERSION_MINOR,
                "data": {
                    "items": [
                        {
                            CONF_ID: "from_storage",
                            CONF_NAME: "from storage",
                            CONF_ICON: "mdi:party-popper",
                            CONF_FRIDAY: [
                                {CONF_FROM: "17:00:00", CONF_TO: "23:59:59"},
                            ],
                            CONF_SATURDAY: [
                                {CONF_FROM: "00:00:00", CONF_TO: "23:59:59"},
                            ],
                            CONF_SUNDAY: [
                                {CONF_FROM: "00:00:00", CONF_TO: "24:00:00"},
                            ],
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "minor_version": STORAGE_VERSION_MINOR,
                "data": {"items": items},
            }
        if config is None:
            config = {
                DOMAIN: {
                    "from_yaml": {
                        CONF_NAME: "from yaml",
                        CONF_ICON: "mdi:party-pooper",
                        CONF_MONDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_TUESDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_WEDNESDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_THURSDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_FRIDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_SATURDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                        CONF_SUNDAY: [{CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}],
                    }
                }
            }
        return await async_setup_component(hass, DOMAIN, config)

    return _schedule_setup


async def test_invalid_config(hass: HomeAssistant) -> None:
    """Test invalid configs."""
    invalid_configs = [
        None,
        {},
        {"name with space": None},
    ]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


@pytest.mark.parametrize(
    ("schedule", "error"),
    (
        (
            [
                {CONF_FROM: "00:00:00", CONF_TO: "23:59:59"},
                {CONF_FROM: "07:00:00", CONF_TO: "08:00:00"},
            ],
            "Overlapping times found in schedule",
        ),
        (
            [
                {CONF_FROM: "07:00:00", CONF_TO: "08:00:00"},
                {CONF_FROM: "07:00:00", CONF_TO: "08:00:00"},
            ],
            "Overlapping times found in schedule",
        ),
        (
            [
                {CONF_FROM: "07:59:00", CONF_TO: "09:00:00"},
                {CONF_FROM: "07:00:00", CONF_TO: "08:00:00"},
            ],
            "Overlapping times found in schedule",
        ),
        (
            [
                {CONF_FROM: "06:00:00", CONF_TO: "07:00:00"},
                {CONF_FROM: "06:59:00", CONF_TO: "08:00:00"},
            ],
            "Overlapping times found in schedule",
        ),
        (
            [
                {CONF_FROM: "06:00:00", CONF_TO: "05:00:00"},
            ],
            "Invalid time range, from 06:00:00 is after 05:00:00",
        ),
    ),
)
async def test_invalid_schedules(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    caplog: pytest.LogCaptureFixture,
    schedule: list[dict[str, str]],
    error: str,
) -> None:
    """Test overlapping time ranges invalidate."""
    assert not await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-pooper",
                    CONF_SUNDAY: schedule,
                }
            }
        }
    )
    assert error in caplog.text


async def test_events_one_day(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    caplog: pytest.LogCaptureFixture,
    freezer,
) -> None:
    """Test events only during one day of the week."""
    freezer.move_to("2022-08-30 13:20:00-07:00")

    assert await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-popper",
                    CONF_SUNDAY: {CONF_FROM: "07:00:00", CONF_TO: "11:00:00"},
                }
            }
        },
        items=[],
    )

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T07:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T11:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-11T07:00:00-07:00"


async def test_adjacent_cross_midnight(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    caplog: pytest.LogCaptureFixture,
    freezer,
) -> None:
    """Test adjacent events don't toggle on->off->on."""
    freezer.move_to("2022-08-30 13:20:00-07:00")

    assert await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-popper",
                    CONF_SUNDAY: {CONF_FROM: "23:00:00", CONF_TO: "24:00:00"},
                    CONF_MONDAY: {CONF_FROM: "00:00:00", CONF_TO: "01:00:00"},
                }
            }
        },
        items=[],
    )

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T23:00:00-07:00"

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-05T00:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-05T01:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-11T23:00:00-07:00"

    await hass.async_block_till_done()
    assert len(state_changes) == 3
    for event in state_changes[:-1]:
        assert event.data["new_state"].state == STATE_ON
    assert state_changes[2].data["new_state"].state == STATE_OFF


async def test_adjacent_within_day(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    caplog: pytest.LogCaptureFixture,
    freezer,
) -> None:
    """Test adjacent events don't toggle on->off->on."""
    freezer.move_to("2022-08-30 13:20:00-07:00")

    assert await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-popper",
                    CONF_SUNDAY: [
                        {CONF_FROM: "22:00:00", CONF_TO: "22:30:00"},
                        {CONF_FROM: "22:30:00", CONF_TO: "23:00:00"},
                    ],
                }
            }
        },
        items=[],
    )

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T22:00:00-07:00"

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T22:30:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T23:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-11T22:00:00-07:00"

    await hass.async_block_till_done()
    assert len(state_changes) == 3
    for event in state_changes[:-1]:
        assert event.data["new_state"].state == STATE_ON
    assert state_changes[2].data["new_state"].state == STATE_OFF


async def test_non_adjacent_within_day(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    caplog: pytest.LogCaptureFixture,
    freezer,
) -> None:
    """Test adjacent events don't toggle on->off->on."""
    freezer.move_to("2022-08-30 13:20:00-07:00")

    assert await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-popper",
                    CONF_SUNDAY: [
                        {CONF_FROM: "22:00:00", CONF_TO: "22:15:00"},
                        {CONF_FROM: "22:30:00", CONF_TO: "23:00:00"},
                    ],
                }
            }
        },
        items=[],
    )

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T22:00:00-07:00"

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T22:15:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T22:30:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T23:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-11T22:00:00-07:00"

    await hass.async_block_till_done()
    assert len(state_changes) == 4
    assert state_changes[0].data["new_state"].state == STATE_ON
    assert state_changes[1].data["new_state"].state == STATE_OFF
    assert state_changes[2].data["new_state"].state == STATE_ON
    assert state_changes[3].data["new_state"].state == STATE_OFF


@pytest.mark.parametrize(
    "schedule",
    (
        {CONF_FROM: "00:00:00", CONF_TO: "24:00"},
        {CONF_FROM: "00:00:00", CONF_TO: "24:00:00"},
    ),
)
async def test_to_midnight(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    caplog: pytest.LogCaptureFixture,
    schedule: list[dict[str, str]],
    freezer,
) -> None:
    """Test time range allow to 24:00."""
    freezer.move_to("2022-08-30 13:20:00-07:00")

    assert await schedule_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "from yaml",
                    CONF_ICON: "mdi:party-popper",
                    CONF_SUNDAY: schedule,
                }
            }
        },
        items=[],
    )

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-04T00:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-05T00:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-09-11T00:00:00-07:00"


async def test_setup_no_config(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test component setup with no config."""
    count_start = len(hass.states.async_entity_ids())
    assert await async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.config.load_yaml_config_file", autospec=True, return_value={}
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start == len(hass.states.async_entity_ids())


@pytest.mark.freeze_time("2022-08-10 20:10:00-07:00")
async def test_load(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test set up from storage and YAML."""
    assert await schedule_setup()

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from storage"
    assert state.attributes[ATTR_EDITABLE] is True
    assert state.attributes[ATTR_ICON] == "mdi:party-popper"
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T17:00:00-07:00"

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from yaml"
    assert state.attributes[ATTR_EDITABLE] is False
    assert state.attributes[ATTR_ICON] == "mdi:party-pooper"
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-10T23:59:59-07:00"


async def test_schedule_updates(
    hass: HomeAssistant,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    freezer,
) -> None:
    """Test the schedule updates when time changes."""
    freezer.move_to("2022-08-10 20:10:00-07:00")
    assert await schedule_setup()

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T17:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T23:59:59-07:00"


async def test_ws_list(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test listing via WS."""
    assert await schedule_setup()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert result["from_storage"][ATTR_NAME] == "from storage"
    assert result["from_storage"][CONF_FRIDAY] == [
        {CONF_FROM: "17:00:00", CONF_TO: "23:59:59"}
    ]
    assert result["from_storage"][CONF_SATURDAY] == [
        {CONF_FROM: "00:00:00", CONF_TO: "23:59:59"}
    ]
    assert result["from_storage"][CONF_SUNDAY] == [
        {CONF_FROM: "00:00:00", CONF_TO: "24:00:00"}
    ]
    assert "from_yaml" not in result


async def test_ws_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
) -> None:
    """Test WS delete cleans up entity registry."""
    ent_reg = er.async_get(hass)

    assert await schedule_setup()

    state = hass.states.get("schedule.from_storage")
    assert state is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": "from_storage"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("schedule.from_storage")
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") is None


@pytest.mark.freeze_time("2022-08-10 20:10:00-07:00")
@pytest.mark.parametrize(
    ("to", "next_event", "saved_to"),
    (
        ("23:59:59", "2022-08-10T23:59:59-07:00", "23:59:59"),
        ("24:00", "2022-08-11T00:00:00-07:00", "24:00:00"),
        ("24:00:00", "2022-08-11T00:00:00-07:00", "24:00:00"),
    ),
)
async def test_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    to: str,
    next_event: str,
    saved_to: str,
) -> None:
    """Test updating the schedule."""
    ent_reg = er.async_get(hass)

    assert await schedule_setup()

    state = hass.states.get("schedule.from_storage")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from storage"
    assert state.attributes[ATTR_ICON] == "mdi:party-popper"
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-12T17:00:00-07:00"
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") is not None

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": "from_storage",
            CONF_NAME: "Party pooper",
            CONF_ICON: "mdi:party-pooper",
            CONF_MONDAY: [],
            CONF_TUESDAY: [],
            CONF_WEDNESDAY: [{CONF_FROM: "17:00:00", CONF_TO: to}],
            CONF_THURSDAY: [],
            CONF_FRIDAY: [],
            CONF_SATURDAY: [],
            CONF_SUNDAY: [],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("schedule.from_storage")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Party pooper"
    assert state.attributes[ATTR_ICON] == "mdi:party-pooper"
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == next_event

    await client.send_json({"id": 2, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert result["from_storage"][CONF_WEDNESDAY] == [
        {CONF_FROM: "17:00:00", CONF_TO: saved_to}
    ]


@pytest.mark.freeze_time("2022-08-11 8:52:00-07:00")
@pytest.mark.parametrize(
    ("to", "next_event", "saved_to"),
    (
        ("14:00:00", "2022-08-15T14:00:00-07:00", "14:00:00"),
        ("24:00", "2022-08-16T00:00:00-07:00", "24:00:00"),
        ("24:00:00", "2022-08-16T00:00:00-07:00", "24:00:00"),
    ),
)
async def test_ws_create(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    schedule_setup: Callable[..., Coroutine[Any, Any, bool]],
    freezer,
    to: str,
    next_event: str,
    saved_to: str,
) -> None:
    """Test create WS."""
    freezer.move_to("2022-08-11 8:52:00-07:00")

    ent_reg = er.async_get(hass)

    assert await schedule_setup(items=[])

    state = hass.states.get("schedule.party_mode")
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "party_mode") is None

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/create",
            "name": "Party mode",
            "icon": "mdi:party-popper",
            "monday": [{"from": "12:00:00", "to": to}],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get("schedule.party_mode")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Party mode"
    assert state.attributes[ATTR_EDITABLE] is True
    assert state.attributes[ATTR_ICON] == "mdi:party-popper"
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == "2022-08-15T12:00:00-07:00"

    freezer.move_to(state.attributes[ATTR_NEXT_EVENT])
    async_fire_time_changed(hass)

    state = hass.states.get("schedule.party_mode")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_EVENT].isoformat() == next_event

    await client.send_json({"id": 2, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert result["party_mode"][CONF_MONDAY] == [
        {CONF_FROM: "12:00:00", CONF_TO: saved_to}
    ]
