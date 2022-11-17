"""Test creating repairs from alerts."""
from __future__ import annotations

from datetime import timedelta
import json
from unittest.mock import ANY, patch

import pytest

from homeassistant.components.homeassistant_alerts import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import assert_lists_same, async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


def stub_alert(aioclient_mock, filename):
    """Stub an alert."""
    aioclient_mock.get(
        f"https://alerts.home-assistant.io/alerts/{filename}",
        text=f"""---
title: Title for {filename}
---
Content for {filename}
""",
    )


@pytest.fixture(autouse=True)
async def setup_repairs(hass):
    """Set up the repairs integration."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})


@pytest.mark.parametrize(
    "ha_version, expected_alerts",
    (
        (
            "2022.7.0",
            [
                ("aladdin_connect.markdown", "aladdin_connect"),
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
                ("hikvision.markdown", "hikvisioncam"),
                ("hive_us.markdown", "hive"),
                ("homematicip_cloud.markdown", "homematicip_cloud"),
                ("logi_circle.markdown", "logi_circle"),
                ("neato.markdown", "neato"),
                ("nest.markdown", "nest"),
                ("senseme.markdown", "senseme"),
                ("sochain.markdown", "sochain"),
            ],
        ),
        (
            "2022.8.0",
            [
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
                ("hikvision.markdown", "hikvisioncam"),
                ("hive_us.markdown", "hive"),
                ("homematicip_cloud.markdown", "homematicip_cloud"),
                ("logi_circle.markdown", "logi_circle"),
                ("neato.markdown", "neato"),
                ("nest.markdown", "nest"),
                ("senseme.markdown", "senseme"),
                ("sochain.markdown", "sochain"),
            ],
        ),
        (
            "2021.10.0",
            [
                ("aladdin_connect.markdown", "aladdin_connect"),
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
                ("hikvision.markdown", "hikvisioncam"),
                ("homematicip_cloud.markdown", "homematicip_cloud"),
                ("logi_circle.markdown", "logi_circle"),
                ("neato.markdown", "neato"),
                ("nest.markdown", "nest"),
                ("senseme.markdown", "senseme"),
                ("sochain.markdown", "sochain"),
            ],
        ),
    ),
)
async def test_alerts(
    hass: HomeAssistant,
    hass_ws_client,
    aioclient_mock: AiohttpClientMocker,
    ha_version,
    expected_alerts,
) -> None:
    """Test creating issues based on alerts."""

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://alerts.home-assistant.io/alerts.json",
        text=load_fixture("alerts_1.json", "homeassistant_alerts"),
    )
    for alert in expected_alerts:
        stub_alert(aioclient_mock, alert[0])

    activated_components = (
        "aladdin_connect",
        "darksky",
        "hikvision",
        "hikvisioncam",
        "hive",
        "homematicip_cloud",
        "logi_circle",
        "neato",
        "nest",
        "senseme",
        "sochain",
    )
    for domain in activated_components:
        hass.config.components.add(domain)

    with patch(
        "homeassistant.components.homeassistant_alerts.__version__",
        ha_version,
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "homeassistant_alerts",
                "ignored": False,
                "is_fixable": False,
                "issue_id": f"{alert}_{integration}",
                "issue_domain": integration,
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "alert",
                "translation_placeholders": {
                    "title": f"Title for {alert}",
                    "description": f"Content for {alert}",
                },
            }
            for alert, integration in expected_alerts
        ]
    }


@pytest.mark.parametrize(
    "ha_version, fixture, expected_alerts",
    (
        (
            "2022.7.0",
            "alerts_no_integrations.json",
            [
                ("dark_sky.markdown", "darksky"),
            ],
        ),
        (
            "2022.7.0",
            "alerts_no_package.json",
            [
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
            ],
        ),
    ),
)
async def test_bad_alerts(
    hass: HomeAssistant,
    hass_ws_client,
    aioclient_mock: AiohttpClientMocker,
    ha_version,
    fixture,
    expected_alerts,
) -> None:
    """Test creating issues based on alerts."""
    fixture_content = load_fixture(fixture, "homeassistant_alerts")
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://alerts.home-assistant.io/alerts.json",
        text=fixture_content,
    )
    for alert in json.loads(fixture_content):
        stub_alert(aioclient_mock, alert["filename"])

    activated_components = (
        "darksky",
        "hikvision",
        "hikvisioncam",
    )
    for domain in activated_components:
        hass.config.components.add(domain)

    with patch(
        "homeassistant.components.homeassistant_alerts.__version__",
        ha_version,
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "issues": [
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "homeassistant_alerts",
                "ignored": False,
                "is_fixable": False,
                "issue_id": f"{alert}_{integration}",
                "issue_domain": integration,
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "alert",
                "translation_placeholders": {
                    "title": f"Title for {alert}",
                    "description": f"Content for {alert}",
                },
            }
            for alert, integration in expected_alerts
        ]
    }


async def test_no_alerts(
    hass: HomeAssistant,
    hass_ws_client,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test creating issues based on alerts."""

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://alerts.home-assistant.io/alerts.json",
        text="",
    )

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"issues": []}


@pytest.mark.parametrize(
    "ha_version, fixture_1, expected_alerts_1, fixture_2, expected_alerts_2",
    (
        (
            "2022.7.0",
            "alerts_1.json",
            [
                ("aladdin_connect.markdown", "aladdin_connect"),
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
                ("hikvision.markdown", "hikvisioncam"),
                ("hive_us.markdown", "hive"),
                ("homematicip_cloud.markdown", "homematicip_cloud"),
                ("logi_circle.markdown", "logi_circle"),
                ("neato.markdown", "neato"),
                ("nest.markdown", "nest"),
                ("senseme.markdown", "senseme"),
                ("sochain.markdown", "sochain"),
            ],
            "alerts_2.json",
            [
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
                ("hikvision.markdown", "hikvisioncam"),
                ("hive_us.markdown", "hive"),
                ("homematicip_cloud.markdown", "homematicip_cloud"),
                ("logi_circle.markdown", "logi_circle"),
                ("neato.markdown", "neato"),
                ("nest.markdown", "nest"),
                ("senseme.markdown", "senseme"),
                ("sochain.markdown", "sochain"),
            ],
        ),
        (
            "2022.7.0",
            "alerts_2.json",
            [
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
                ("hikvision.markdown", "hikvisioncam"),
                ("hive_us.markdown", "hive"),
                ("homematicip_cloud.markdown", "homematicip_cloud"),
                ("logi_circle.markdown", "logi_circle"),
                ("neato.markdown", "neato"),
                ("nest.markdown", "nest"),
                ("senseme.markdown", "senseme"),
                ("sochain.markdown", "sochain"),
            ],
            "alerts_1.json",
            [
                ("aladdin_connect.markdown", "aladdin_connect"),
                ("dark_sky.markdown", "darksky"),
                ("hikvision.markdown", "hikvision"),
                ("hikvision.markdown", "hikvisioncam"),
                ("hive_us.markdown", "hive"),
                ("homematicip_cloud.markdown", "homematicip_cloud"),
                ("logi_circle.markdown", "logi_circle"),
                ("neato.markdown", "neato"),
                ("nest.markdown", "nest"),
                ("senseme.markdown", "senseme"),
                ("sochain.markdown", "sochain"),
            ],
        ),
    ),
)
async def test_alerts_change(
    hass: HomeAssistant,
    hass_ws_client,
    aioclient_mock: AiohttpClientMocker,
    ha_version: str,
    fixture_1: str,
    expected_alerts_1: list[tuple(str, str)],
    fixture_2: str,
    expected_alerts_2: list[tuple(str, str)],
) -> None:
    """Test creating issues based on alerts."""
    fixture_1_content = load_fixture(fixture_1, "homeassistant_alerts")
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://alerts.home-assistant.io/alerts.json",
        text=fixture_1_content,
    )
    for alert in json.loads(fixture_1_content):
        stub_alert(aioclient_mock, alert["filename"])

    activated_components = (
        "aladdin_connect",
        "darksky",
        "hikvision",
        "hikvisioncam",
        "hive",
        "homematicip_cloud",
        "logi_circle",
        "neato",
        "nest",
        "senseme",
        "sochain",
    )
    for domain in activated_components:
        hass.config.components.add(domain)

    with patch(
        "homeassistant.components.homeassistant_alerts.__version__",
        ha_version,
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    now = dt_util.utcnow()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert_lists_same(
        msg["result"]["issues"],
        [
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "homeassistant_alerts",
                "ignored": False,
                "is_fixable": False,
                "issue_id": f"{alert}_{integration}",
                "issue_domain": integration,
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "alert",
                "translation_placeholders": {
                    "title": f"Title for {alert}",
                    "description": f"Content for {alert}",
                },
            }
            for alert, integration in expected_alerts_1
        ],
    )

    fixture_2_content = load_fixture(fixture_2, "homeassistant_alerts")
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://alerts.home-assistant.io/alerts.json",
        text=fixture_2_content,
    )
    for alert in json.loads(fixture_2_content):
        stub_alert(aioclient_mock, alert["filename"])

    future = now + UPDATE_INTERVAL + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    await client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await client.receive_json()
    assert msg["success"]
    assert_lists_same(
        msg["result"]["issues"],
        [
            {
                "breaks_in_ha_version": None,
                "created": ANY,
                "dismissed_version": None,
                "domain": "homeassistant_alerts",
                "ignored": False,
                "is_fixable": False,
                "issue_id": f"{alert}_{integration}",
                "issue_domain": integration,
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "alert",
                "translation_placeholders": {
                    "title": f"Title for {alert}",
                    "description": f"Content for {alert}",
                },
            }
            for alert, integration in expected_alerts_2
        ],
    )
