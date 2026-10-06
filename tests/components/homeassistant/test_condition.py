"""Tests for the Home Assistant date condition."""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest

from homeassistant.components import automation
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import condition, trace
from homeassistant.setup import async_setup_component

from tests.components.common import assert_condition_options_supported
from tests.typing import MockHAClientWebSocket, WebSocketGenerator

CONDITION = "homeassistant.date"
WINTER = {"start": "10-01", "end": "03-31"}
HOLIDAYS = {"start": "12-24", "end": "01-06"}
SUMMER = {"start": "06-01", "end": "08-31"}
CHRISTMAS_DAY = {"start": "12-25", "end": "12-25"}


@pytest.fixture(autouse=True)
def prepare_condition_trace() -> None:
    """Clear previous trace."""
    trace.trace_clear()


async def _evaluate(hass: HomeAssistant, options: dict[str, str]) -> bool | None:
    """Validate and evaluate a date condition."""
    config = await condition.async_validate_condition_config(
        hass, {"condition": CONDITION, "options": options}
    )
    checker = await condition.async_from_config(hass, config)
    return checker(hass)


@pytest.mark.parametrize(
    ("options", "now", "expected"),
    [
        pytest.param(WINTER, "2026-10-01", True, id="wrap_start"),
        pytest.param(WINTER, "2026-12-15", True, id="wrap_inside"),
        pytest.param(WINTER, "2027-03-31", True, id="wrap_end"),
        pytest.param(WINTER, "2027-04-01", False, id="wrap_after"),
        pytest.param(WINTER, "2026-09-30", False, id="wrap_before"),
        pytest.param(HOLIDAYS, "2026-12-24", True, id="holidays_start"),
        pytest.param(HOLIDAYS, "2027-01-06", True, id="holidays_end"),
        pytest.param(HOLIDAYS, "2027-01-07", False, id="holidays_after"),
        pytest.param(SUMMER, "2026-07-15", True, id="inside"),
        pytest.param(SUMMER, "2026-09-01", False, id="outside"),
        pytest.param(CHRISTMAS_DAY, "2026-12-25", True, id="single_day"),
        pytest.param(CHRISTMAS_DAY, "2026-12-26", False, id="not_the_day"),
        pytest.param({"start": "10-01"}, "2026-12-31", True, id="start_only_inside"),
        pytest.param({"start": "10-01"}, "2026-01-01", False, id="start_only_outside"),
        pytest.param({"end": "03-31"}, "2026-01-01", True, id="end_only_inside"),
        pytest.param({"end": "03-31"}, "2026-04-01", False, id="end_only_outside"),
        pytest.param(
            {"start": "02-29", "end": "02-29"}, "2027-02-28", False, id="leap_day_off"
        ),
        pytest.param(
            {"start": "02-28", "end": "03-01"}, "2028-02-29", True, id="leap_day_in"
        ),
    ],
)
async def test_date_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    options: dict[str, str],
    now: str,
    expected: bool,
) -> None:
    """Test date condition windows."""
    freezer.move_to(f"{now} 20:00:00+00:00")

    assert await _evaluate(hass, options) is expected


async def test_date_uses_local_date(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the condition compares against the local date, not the UTC date."""
    # Shortly after midnight UTC on January 1 it is still December 31 in US/Pacific
    freezer.move_to("2027-01-01 02:00:00+00:00")

    assert await _evaluate(hass, {"start": "12-31", "end": "12-31"}) is True
    assert await _evaluate(hass, {"start": "01-01", "end": "01-01"}) is False


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({}, id="empty"),
        pytest.param({"unknown": True}, id="unknown_option"),
        pytest.param({"start": "2026-12-24"}, id="full_date"),
        pytest.param({"start": "12-24", "end": "1-6"}, id="unpadded"),
        pytest.param({"start": "02-30"}, id="invalid_day"),
    ],
)
async def test_date_invalid_options(
    hass: HomeAssistant, options: dict[str, Any]
) -> None:
    """Test invalid date condition options are rejected."""
    with pytest.raises(probatio.Invalid):
        await condition.async_validate_condition_config(
            hass, {"condition": CONDITION, "options": options}
        )


async def test_date_options_supported(hass: HomeAssistant) -> None:
    """Test the date condition options match its description."""
    await assert_condition_options_supported(
        hass,
        CONDITION,
        {"start": "12-24"},
        supports_behavior=False,
        supports_duration=False,
        supports_target=False,
    )


async def _get_automation_condition_trace(
    client: MockHAClientWebSocket, automation_id: str
) -> dict[str, Any]:
    """Return the condition trace of the newest run of an automation."""
    await client.send_json_auto_id({"type": "trace/list", "domain": "automation"})
    response = await client.receive_json()
    assert response["success"]
    run_id = next(
        item["run_id"]
        for item in reversed(response["result"])
        if item["item_id"] == automation_id
    )

    await client.send_json_auto_id(
        {
            "type": "trace/get",
            "domain": "automation",
            "item_id": automation_id,
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    condition_traces = response["result"]["trace"]["condition/0"]
    assert len(condition_traces) == 1
    return condition_traces[0]["result"]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        pytest.param("2026-12-25", True, id="inside"),
        pytest.param("2026-07-01", False, id="outside"),
    ],
)
async def test_date_automation_trace(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
    now: str,
    expected: bool,
) -> None:
    """Test the date condition in an automation, including its trace."""
    # Authenticate before moving time, the access token expires otherwise
    client = await hass_ws_client()
    freezer.move_to(f"{now} 20:00:00+00:00")
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "holidays",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": CONDITION, "options": HOLIDAYS},
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert len(service_calls) == (1 if expected else 0)
    assert await _get_automation_condition_trace(client, "holidays") == {
        "result": expected,
        "start": "12-24",
        "now_date": now,
        "end": "01-06",
    }
