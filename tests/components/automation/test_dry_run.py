"""Tests for the automation dry run websocket command."""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import automation
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_ID = "automation.hello"
EVENT_TRIGGER = {"trigger": "event", "event_type": "test_event"}
ACTIONS = {"action": "test.automation"}
FULL_CONFIG = {
    "triggers": [
        {"trigger": "state", "entity_id": "light.kitchen", "to": "on"},
        {
            "trigger": "state",
            "entity_id": "light.kitchen",
            "to": "on",
            "for": {"minutes": 15},
        },
        {
            "trigger": "numeric_state",
            "entity_id": "sensor.temperature",
            "above": 25,
        },
        {"trigger": "time", "at": ["07:00:00", "22:00:00"], "weekday": "mon"},
        {**EVENT_TRIGGER, "id": "event"},
        {**EVENT_TRIGGER, "enabled": False},
        {
            "trigger": "numeric_state",
            "entity_id": "sensor.temperature",
            "above": 25,
            "value_template": "{{ state.state | float * 2 }}",
        },
        {
            "trigger": "state",
            "entity_id": "light.kitchen",
            "to": "off",
            "for": {"minutes": "{{ 15 }}"},
        },
        {"trigger": "time", "at": ["input_datetime.wake_up", "07:00:00"]},
    ],
    "variables": {
        "target": 20,
        "new_state": "{{ trigger.to_state.state }}",
        "is_on": "{{ new_state == 'on' }}",
    },
    "conditions": [
        {"condition": "state", "entity_id": "light.kitchen", "state": "off"},
        {
            "condition": "numeric_state",
            "entity_id": "sensor.temperature",
            "above": 20,
        },
        "{{ states('sensor.temperature') | float > target }}",
        {
            "condition": "or",
            "alias": "Trigger or light",
            "conditions": [
                "{{ trigger.id == 'event' }}",
                {"condition": "state", "entity_id": "light.kitchen", "state": "on"},
            ],
        },
        {
            "condition": "not",
            "conditions": [
                {"condition": "template", "value_template": "{{ is_on }}"},
            ],
        },
        {"condition": "trigger", "id": "event"},
        {
            "condition": "state",
            "entity_id": "light.kitchen",
            "state": "off",
            "enabled": False,
        },
        {"condition": "template", "value_template": "{{ states.light.x.state }}"},
        {
            "condition": "state",
            "entity_id": "light.kitchen",
            "state": "off",
            "enabled": "{{ target is defined }}",
        },
    ],
    "actions": ACTIONS,
}


@pytest.fixture(autouse=True)
async def setup_states(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Set up the time zone, a fixed time and the states the tests read."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-05 10:00:00+01:00")
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("sensor.temperature", "21.5")
    freezer.tick(600)


async def _async_dry_run(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config: dict[str, Any],
    entity_id: str = ENTITY_ID,
) -> dict[str, Any]:
    """Set up an automation and dry run it."""
    assert await async_setup_component(
        hass, automation.DOMAIN, {automation.DOMAIN: {"alias": "hello", **config}}
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "automation/dry_run", "entity_id": entity_id}
    )
    return await client.receive_json()


async def test_dry_run(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a dry run explains every trigger and condition."""
    msg = await _async_dry_run(hass, hass_ws_client, FULL_CONFIG)

    assert msg["success"]
    assert msg["result"] == snapshot


@pytest.mark.parametrize(
    ("config", "would_run", "reason"),
    [
        pytest.param(
            {
                "triggers": EVENT_TRIGGER,
                "conditions": {
                    "condition": "state",
                    "entity_id": "light.kitchen",
                    "state": "on",
                },
            },
            True,
            None,
            id="conditions_pass",
        ),
        pytest.param({"triggers": EVENT_TRIGGER}, True, None, id="no_conditions"),
        pytest.param(
            {
                "triggers": EVENT_TRIGGER,
                "conditions": {
                    "condition": "state",
                    "entity_id": "light.kitchen",
                    "state": "off",
                },
            },
            False,
            "conditions_not_met",
            id="conditions_not_met",
        ),
        pytest.param(
            {
                "triggers": EVENT_TRIGGER,
                "conditions": {"condition": "trigger", "id": "0"},
            },
            None,
            "depends_on_trigger",
            id="depends_on_trigger",
        ),
        pytest.param(
            {
                "triggers": EVENT_TRIGGER,
                "conditions": [
                    {"condition": "trigger", "id": "0"},
                    {
                        "condition": "state",
                        "entity_id": "light.kitchen",
                        "state": "off",
                    },
                ],
            },
            False,
            "conditions_not_met",
            id="failing_condition_beats_trigger_dependency",
        ),
        pytest.param(
            {
                "triggers": EVENT_TRIGGER,
                "conditions": {
                    "condition": "numeric_state",
                    "entity_id": "light.kitchen",
                    "above": 5,
                },
            },
            False,
            "condition_error",
            id="condition_error",
        ),
        pytest.param(
            {"initial_state": False, "triggers": EVENT_TRIGGER},
            False,
            "automation_off",
            id="automation_off",
        ),
        pytest.param(
            {"triggers": {**EVENT_TRIGGER, "enabled": False}},
            True,
            None,
            id="no_enabled_triggers",
        ),
        pytest.param({"triggers": []}, True, None, id="no_triggers"),
    ],
)
async def test_dry_run_verdict(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config: dict[str, Any],
    would_run: bool | None,
    reason: str | None,
) -> None:
    """Test the overall verdict of a dry run."""
    msg = await _async_dry_run(hass, hass_ws_client, {**config, "actions": ACTIONS})

    assert msg["success"]
    assert msg["result"]["would_run"] is would_run
    assert msg["result"]["reason"] == reason


@pytest.mark.parametrize(
    ("mode", "runs", "reason"),
    [
        pytest.param({"mode": "single"}, 1, "already_running", id="single"),
        pytest.param({"mode": "restart"}, 1, None, id="restart"),
        pytest.param({"mode": "parallel", "max": 2}, 1, None, id="below_max"),
        pytest.param(
            {"mode": "parallel", "max": 2}, 2, "max_runs_reached", id="max_reached"
        ),
    ],
)
async def test_dry_run_running(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mode: dict[str, Any],
    runs: int,
    reason: str | None,
) -> None:
    """Test the verdict while the automation is already running."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "triggers": EVENT_TRIGGER,
                "actions": {"wait_template": "{{ false }}"},
                **mode,
            }
        },
    )
    client = await hass_ws_client(hass)
    # The run waits forever, block_till_done would never return
    for _ in range(runs):
        hass.bus.async_fire("test_event")

    await client.send_json_auto_id(
        {"type": "automation/dry_run", "entity_id": ENTITY_ID}
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["current_runs"] == runs
    assert msg["result"]["reason"] == reason


@pytest.mark.parametrize(
    ("entity_id", "code"),
    [
        pytest.param("automation.not_exist", "not_found", id="not_found"),
        pytest.param(ENTITY_ID, "not_supported", id="invalid_config"),
    ],
)
async def test_dry_run_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    code: str,
) -> None:
    """Test a dry run of a missing or invalid automation."""
    msg = await _async_dry_run(
        hass,
        hass_ws_client,
        {"triggers": {"trigger": "event"}, "actions": ACTIONS},
        entity_id,
    )

    assert not msg["success"]
    assert msg["error"]["code"] == code


async def test_dry_run_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test the dry run command requires an admin."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "triggers": EVENT_TRIGGER,
                "actions": ACTIONS,
            }
        },
    )
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id(
        {"type": "automation/dry_run", "entity_id": ENTITY_ID}
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def _async_dry_run_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, config: dict[str, Any]
) -> dict[str, Any]:
    """Dry run an unsaved automation config."""
    assert await async_setup_component(hass, automation.DOMAIN, {})
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "automation/dry_run", "config": config})
    return await client.receive_json()


async def test_dry_run_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test an unsaved config gives the same result as the saved automation."""
    entity_msg = await _async_dry_run(hass, hass_ws_client, FULL_CONFIG)

    msg = await _async_dry_run_config(hass, hass_ws_client, FULL_CONFIG)

    assert msg["success"]
    assert msg["result"] == {
        key: value for key, value in entity_msg["result"].items() if key != "entity_id"
    }


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            {"mode": "parallel", "max": 3},
            {"enabled": True, "mode": "parallel", "current_runs": 0, "max_runs": 3},
            id="parallel",
        ),
        pytest.param(
            {"initial_state": False},
            {"enabled": True, "mode": "single", "current_runs": 0, "max_runs": None},
            id="initial_state_off",
        ),
    ],
)
async def test_dry_run_config_mode(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test an unsaved config takes its mode from the config and has no runs."""
    msg = await _async_dry_run_config(
        hass,
        hass_ws_client,
        {
            "triggers": EVENT_TRIGGER,
            "conditions": "{{ this is none }}",
            "actions": ACTIONS,
            **config,
        },
    )

    assert msg["success"]
    assert (
        msg["result"].items()
        >= {
            **expected,
            "would_run": True,
            "reason": None,
        }.items()
    )


@pytest.mark.parametrize(
    ("config", "message"),
    [
        pytest.param(
            {"actions": ACTIONS},
            "required key not provided at 'triggers'",
            id="missing_triggers",
        ),
        pytest.param(
            {"triggers": {"trigger": "not_a_platform"}, "actions": ACTIONS},
            "Invalid trigger 'not_a_platform' specified",
            id="invalid_trigger",
        ),
        pytest.param(
            {
                "triggers": EVENT_TRIGGER,
                "conditions": {"condition": "state", "state": "on"},
                "actions": ACTIONS,
            },
            "required key not provided at 'conditions[0].entity_id'",
            id="invalid_condition",
        ),
    ],
)
async def test_dry_run_config_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config: dict[str, Any],
    message: str,
) -> None:
    """Test an invalid unsaved config gives a readable error."""
    msg = await _async_dry_run_config(hass, hass_ws_client, config)

    assert not msg["success"]
    assert msg["error"] == {"code": "invalid_format", "message": message}


@pytest.mark.parametrize(
    "target",
    [
        pytest.param({}, id="neither"),
        pytest.param(
            {"entity_id": ENTITY_ID, "config": {"triggers": [], "actions": []}},
            id="both",
        ),
    ],
)
async def test_dry_run_needs_one_target(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    target: dict[str, Any],
) -> None:
    """Test the command takes exactly one of entity_id and config."""
    assert await async_setup_component(hass, automation.DOMAIN, {})
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "automation/dry_run", **target})
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
