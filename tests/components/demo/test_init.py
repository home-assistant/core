"""The tests for the Demo component."""
import datetime
from http import HTTPStatus
import json
from unittest.mock import ANY, patch

import pytest

from homeassistant.components.demo import DOMAIN
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    list_statistic_ids,
)
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture(autouse=True)
def mock_history(hass):
    """Mock history component loaded."""
    hass.config.components.add("history")


@pytest.fixture(autouse=True)
def mock_device_tracker_update_config(hass):
    """Prevent device tracker from creating known devices file."""
    with patch("homeassistant.components.device_tracker.legacy.update_config"):
        yield


async def test_setting_up_demo(hass):
    """Test if we can set up the demo and dump it to JSON."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await hass.async_start()

    # This is done to make sure entity components don't accidentally store
    # non-JSON-serializable data in the state machine.
    try:
        json.dumps(hass.states.async_all(), cls=JSONEncoder)
    except Exception:  # pylint: disable=broad-except
        pytest.fail(
            "Unable to convert all demo entities to JSON. "
            "Wrong data in state machine!"
        )


async def test_demo_statistics(hass, recorder_mock):
    """Test that the demo components makes some statistics available."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await hass.async_start()
    await async_wait_recording_done(hass)

    statistic_ids = await get_instance(hass).async_add_executor_job(
        list_statistic_ids, hass
    )
    assert {
        "display_unit_of_measurement": "°C",
        "has_mean": True,
        "has_sum": False,
        "name": "Outdoor temperature",
        "source": "demo",
        "statistic_id": "demo:temperature_outdoor",
        "statistics_unit_of_measurement": "°C",
    } in statistic_ids
    assert {
        "display_unit_of_measurement": "kWh",
        "has_mean": False,
        "has_sum": True,
        "name": "Energy consumption 1",
        "source": "demo",
        "statistic_id": "demo:energy_consumption_kwh",
        "statistics_unit_of_measurement": "kWh",
    } in statistic_ids


async def test_demo_statistics_growth(hass, recorder_mock):
    """Test that the demo sum statistics adds to the previous state."""
    now = dt_util.now()
    last_week = now - datetime.timedelta(days=7)
    last_week_midnight = last_week.replace(hour=0, minute=0, second=0, microsecond=0)

    statistic_id = f"{DOMAIN}:energy_consumption_kwh"
    metadata = {
        "source": DOMAIN,
        "name": "Energy consumption 1",
        "statistic_id": statistic_id,
        "unit_of_measurement": "kWh",
        "has_mean": False,
        "has_sum": True,
    }
    statistics = [
        {
            "start": last_week_midnight,
            "sum": 2**20,
        }
    ]
    async_add_external_statistics(hass, metadata, statistics)
    await async_wait_recording_done(hass)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await hass.async_start()
    await async_wait_recording_done(hass)

    statistics = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, False
    )
    assert statistics[statistic_id][0]["sum"] > 2**20


async def test_issues_created(hass, hass_client, hass_ws_client):
    """Test issues are created and can be fixed."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await hass.async_start()

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": "2023.1.1",
                "created": ANY,
                "dismissed_version": None,
                "domain": "demo",
                "ignored": False,
                "is_fixable": False,
                "issue_id": "transmogrifier_deprecated",
                "issue_domain": None,
                "learn_more_url": "https://en.wiktionary.org/wiki/transmogrifier",
                "severity": "warning",
                "translation_key": "transmogrifier_deprecated",
                "translation_placeholders": None,
            },
            {
                "breaks_in_ha_version": "2023.1.1",
                "created": ANY,
                "dismissed_version": None,
                "domain": "demo",
                "ignored": False,
                "is_fixable": True,
                "issue_id": "out_of_blinker_fluid",
                "issue_domain": None,
                "learn_more_url": "https://www.youtube.com/watch?v=b9rntRxLlbU",
                "severity": "critical",
                "translation_key": "out_of_blinker_fluid",
                "translation_placeholders": None,
            },
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "demo",
                "ignored": False,
                "is_fixable": False,
                "issue_id": "unfixable_problem",
                "issue_domain": None,
                "learn_more_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "severity": "warning",
                "translation_key": "unfixable_problem",
                "translation_placeholders": None,
            },
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "demo",
                "ignored": False,
                "is_fixable": True,
                "issue_domain": None,
                "issue_id": "bad_psu",
                "learn_more_url": "https://www.youtube.com/watch?v=b9rntRxLlbU",
                "severity": "critical",
                "translation_key": "bad_psu",
                "translation_placeholders": None,
            },
        ]
    }

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": "demo", "issue_id": "out_of_blinker_fluid"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": None,
        "errors": None,
        "flow_id": ANY,
        "handler": "demo",
        "last_step": None,
        "step_id": "confirm",
        "type": "form",
    }

    url = f"/api/repairs/issues/fix/{flow_id}"
    resp = await client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "description": None,
        "description_placeholders": None,
        "flow_id": flow_id,
        "handler": "demo",
        "title": "",
        "type": "create_entry",
        "version": 1,
    }

    await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": "2023.1.1",
                "created": ANY,
                "dismissed_version": None,
                "domain": "demo",
                "ignored": False,
                "is_fixable": False,
                "issue_id": "transmogrifier_deprecated",
                "issue_domain": None,
                "learn_more_url": "https://en.wiktionary.org/wiki/transmogrifier",
                "severity": "warning",
                "translation_key": "transmogrifier_deprecated",
                "translation_placeholders": None,
            },
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "demo",
                "ignored": False,
                "is_fixable": False,
                "issue_id": "unfixable_problem",
                "issue_domain": None,
                "learn_more_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "severity": "warning",
                "translation_key": "unfixable_problem",
                "translation_placeholders": None,
            },
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "demo",
                "ignored": False,
                "is_fixable": True,
                "issue_domain": None,
                "issue_id": "bad_psu",
                "learn_more_url": "https://www.youtube.com/watch?v=b9rntRxLlbU",
                "severity": "critical",
                "translation_key": "bad_psu",
                "translation_placeholders": None,
            },
        ]
    }
