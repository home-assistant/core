"""The tests for the Everything but the Kitchen Sink integration."""

import datetime
from http import HTTPStatus
from unittest.mock import ANY

import pytest
import voluptuous as vol

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    list_statistic_ids,
)
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.components.recorder.common import async_wait_recording_done
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture
def mock_history(hass: HomeAssistant) -> None:
    """Mock history component loaded."""
    hass.config.components.add("history")


@pytest.mark.usefixtures("recorder_mock", "mock_history")
async def test_demo_statistics(hass: HomeAssistant) -> None:
    """Test that the kitchen sink component makes some statistics available."""
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
        "source": DOMAIN,
        "statistic_id": f"{DOMAIN}:temperature_outdoor",
        "statistics_unit_of_measurement": "°C",
        "unit_class": "temperature",
    } in statistic_ids
    assert {
        "display_unit_of_measurement": "kWh",
        "has_mean": False,
        "has_sum": True,
        "name": "Energy consumption 1",
        "source": DOMAIN,
        "statistic_id": f"{DOMAIN}:energy_consumption_kwh",
        "statistics_unit_of_measurement": "kWh",
        "unit_class": "energy",
    } in statistic_ids


@pytest.mark.usefixtures("recorder_mock", "mock_history")
async def test_demo_statistics_growth(hass: HomeAssistant) -> None:
    """Test that the kitchen sink sum statistics adds to the previous state."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    now = dt_util.now()
    last_week = now - datetime.timedelta(days=7)
    last_week_midnight = last_week.replace(hour=0, minute=0, second=0, microsecond=0)

    statistic_id = f"{DOMAIN}:energy_consumption_kwh"
    metadata = {
        "source": DOMAIN,
        "name": "Energy consumption 1",
        "statistic_id": statistic_id,
        "unit_of_measurement": "m³",
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
        get_last_statistics, hass, 1, statistic_id, False, {"sum"}
    )
    assert statistics[statistic_id][0]["sum"] > 2**20
    assert statistics[statistic_id][0]["sum"] <= (2**20 + 24)


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.usefixtures("mock_history")
async def test_issues_created(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
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
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
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
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
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
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
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
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
                "ignored": False,
                "is_fixable": True,
                "issue_domain": None,
                "issue_id": "bad_psu",
                "learn_more_url": "https://www.youtube.com/watch?v=b9rntRxLlbU",
                "severity": "critical",
                "translation_key": "bad_psu",
                "translation_placeholders": None,
            },
            {
                "breaks_in_ha_version": None,
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
                "is_fixable": True,
                "issue_domain": None,
                "issue_id": "cold_tea",
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "cold_tea",
                "translation_placeholders": None,
                "ignored": False,
            },
            {
                "breaks_in_ha_version": None,
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": "homeassistant",
                "is_fixable": False,
                "issue_domain": DOMAIN,
                "issue_id": ANY,
                "learn_more_url": None,
                "severity": "error",
                "translation_key": "config_entry_reauth",
                "translation_placeholders": {"name": "Kitchen Sink"},
                "ignored": False,
            },
        ]
    }

    url = "/api/repairs/issues/fix"
    resp = await client.post(
        url, json={"handler": DOMAIN, "issue_id": "out_of_blinker_fluid"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": None,
        "errors": None,
        "flow_id": ANY,
        "handler": DOMAIN,
        "last_step": None,
        "preview": None,
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
        "handler": DOMAIN,
        "type": "create_entry",
    }

    await ws_client.send_json({"id": 4, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": "2023.1.1",
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
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
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
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
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
                "ignored": False,
                "is_fixable": True,
                "issue_domain": None,
                "issue_id": "bad_psu",
                "learn_more_url": "https://www.youtube.com/watch?v=b9rntRxLlbU",
                "severity": "critical",
                "translation_key": "bad_psu",
                "translation_placeholders": None,
            },
            {
                "breaks_in_ha_version": None,
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": DOMAIN,
                "is_fixable": True,
                "issue_domain": None,
                "issue_id": "cold_tea",
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "cold_tea",
                "translation_placeholders": None,
                "ignored": False,
            },
            {
                "breaks_in_ha_version": None,
                "created": "2023-10-21T00:00:00+00:00",
                "dismissed_version": None,
                "domain": "homeassistant",
                "is_fixable": False,
                "issue_domain": DOMAIN,
                "issue_id": ANY,
                "learn_more_url": None,
                "severity": "error",
                "translation_key": "config_entry_reauth",
                "translation_placeholders": {"name": "Kitchen Sink"},
                "ignored": False,
            },
        ]
    }


async def test_service(
    hass: HomeAssistant,
) -> None:
    """Test we can call the service."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, "test_service_1", blocking=True)

    await hass.services.async_call(
        DOMAIN, "test_service_1", {"field_1": 1, "field_2": "auto"}, blocking=True
    )

    await hass.services.async_call(
        DOMAIN,
        "test_service_1",
        {"field_1": 1, "field_2": "auto", "field_3": 1, "field_4": "forwards"},
        blocking=True,
    )
