"""Test repairs for unifiprotect."""

from __future__ import annotations

import pytest

from homeassistant.components.workday.const import CONF_REMOVE_HOLIDAYS, DOMAIN
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import (
    TEST_CONFIG_INCORRECT_COUNTRY,
    TEST_CONFIG_INCORRECT_PROVINCE,
    TEST_CONFIG_REMOVE_DATE,
    TEST_CONFIG_REMOVE_NAMED,
    init_integration,
)

from tests.common import ANY
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_bad_country(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad country."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_INCORRECT_COUNTRY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "bad_country")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": entry.title}
    assert data["step_id"] == "country"

    data = await process_repair_fix_flow(client, flow_id, json={"country": "DE"})

    data = await process_repair_fix_flow(client, flow_id, json={"province": "HB"})

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert not issue


async def test_bad_country_none(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad country with no province."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_INCORRECT_COUNTRY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "bad_country")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": entry.title}
    assert data["step_id"] == "country"

    data = await process_repair_fix_flow(client, flow_id, json={"country": "DE"})

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert not issue


async def test_bad_country_no_province(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad country."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_INCORRECT_COUNTRY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "bad_country")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": entry.title}
    assert data["step_id"] == "country"

    data = await process_repair_fix_flow(client, flow_id, json={"country": "SE"})

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert not issue


async def test_bad_province(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad province."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_INCORRECT_PROVINCE)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_province":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "bad_province")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        CONF_COUNTRY: "DE",
        "title": entry.title,
    }
    assert data["step_id"] == "province"

    data = await process_repair_fix_flow(client, flow_id, json={"province": "BW"})

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_province":
            issue = i
    assert not issue


async def test_bad_province_none(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad province selecting none."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_INCORRECT_PROVINCE)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_province":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "bad_province")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        CONF_COUNTRY: "DE",
        "title": entry.title,
    }
    assert data["step_id"] == "province"

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_province":
            issue = i
    assert not issue


async def test_bad_named_holiday(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fixing bad province selecting none."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_REMOVE_NAMED)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    issues = issue_registry.issues.keys()
    for issue in issues:
        if issue[0] == DOMAIN:
            assert issue[1].startswith("bad_named")

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_named_holiday-1-not_a_holiday":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(
        client, DOMAIN, "bad_named_holiday-1-not_a_holiday"
    )

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        CONF_COUNTRY: "US",
        CONF_REMOVE_HOLIDAYS: "Not a Holiday",
        "title": entry.title,
    }
    assert data["step_id"] == "fix_remove_holiday"

    data = await process_repair_fix_flow(
        client, flow_id, json={"remove_holidays": ["Christmas", "Not exist 2"]}
    )

    assert data["errors"] == {
        CONF_REMOVE_HOLIDAYS: "remove_holiday_error",
    }

    data = await process_repair_fix_flow(
        client, flow_id, json={"remove_holidays": ["Christmas", "Thanksgiving"]}
    )

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_named_holiday-1-not_a_holiday":
            issue = i
    assert not issue


async def test_bad_date_holiday(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fixing bad province selecting none."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_REMOVE_DATE)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    issues = issue_registry.issues.keys()
    for issue in issues:
        if issue[0] == DOMAIN:
            assert issue[1].startswith("bad_date")

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_date_holiday-1-2024_02_05":
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, "bad_date_holiday-1-2024_02_05")

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        CONF_COUNTRY: "US",
        CONF_REMOVE_HOLIDAYS: "2024-02-05",
        "title": entry.title,
    }
    assert data["step_id"] == "fix_remove_holiday"

    data = await process_repair_fix_flow(
        client, flow_id, json={"remove_holidays": ["2024-02-06"]}
    )

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_date_holiday-1-2024_02_05":
            issue = i
    assert not issue
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_date_holiday-1-2024_02_06":
            issue = i
    assert issue


@pytest.mark.parametrize(
    "ignore_missing_translations",
    ["component.workday.issues.issue_1.title"],
)
async def test_other_fixable_issues(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad province selecting none."""
    assert await async_setup_component(hass, "repairs", {})
    await init_integration(hass, TEST_CONFIG_INCORRECT_PROVINCE)

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    issue = {
        "breaks_in_ha_version": "2022.9.0dev0",
        "domain": DOMAIN,
        "issue_id": "issue_1",
        "is_fixable": True,
        "learn_more_url": "",
        "severity": "error",
        "translation_key": "issue_1",
    }
    ir.async_create_issue(
        hass,
        issue["domain"],
        issue["issue_id"],
        breaks_in_ha_version=issue["breaks_in_ha_version"],
        is_fixable=issue["is_fixable"],
        is_persistent=False,
        learn_more_url=None,
        severity=issue["severity"],
        translation_key=issue["translation_key"],
    )

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    results = msg["result"]["issues"]
    assert {
        "breaks_in_ha_version": "2022.9.0dev0",
        "created": ANY,
        "dismissed_version": None,
        "domain": "workday",
        "is_fixable": True,
        "issue_domain": None,
        "issue_id": "issue_1",
        "learn_more_url": None,
        "severity": "error",
        "translation_key": "issue_1",
        "translation_placeholders": None,
        "ignored": False,
    } in results

    data = await start_repair_fix_flow(client, DOMAIN, "issue_1")

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()
