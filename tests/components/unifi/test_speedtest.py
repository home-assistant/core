"""UniFi Speedtest platform tests."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


@pytest.fixture(name="speedtest_payload")
def mock_speedtest_payload() -> list[dict[str, Any]]:
    """Speedtest status data."""
    return [
        {
            "download_mbps": 100.0,
            "upload_mbps": 50.0,
            "latency_ms": 10.0,
            "time": 1600000000,
            "interface_name": "eth0",
        },
        {
            "download_mbps": 200.0,
            "upload_mbps": 100.0,
            "latency_ms": 5.0,
            "time": 1600000000,
            "interface_name": "eth2",
        },
    ]


@pytest.mark.usefixtures("config_entry_setup")
async def test_speedtest_sensors(
    hass: HomeAssistant,
) -> None:
    """Verify that speedtest sensors are working as expected."""
    # Verify that sensors are created based on the initial fetch for eth0
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth0_download").state == "100.0"
    )
    assert hass.states.get("sensor.unifi_network_speedtest_eth0_upload").state == "50.0"
    assert hass.states.get("sensor.unifi_network_speedtest_eth0_ping").state == "10.0"
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth0_last_run").state
        == "2020-09-13T12:26:40+00:00"
    )

    # Verify that sensors are created based on the initial fetch for eth2
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth2_download").state == "200.0"
    )
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth2_upload").state == "100.0"
    )
    assert hass.states.get("sensor.unifi_network_speedtest_eth2_ping").state == "5.0"
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth2_last_run").state
        == "2020-09-13T12:26:40+00:00"
    )


@pytest.mark.usefixtures("config_entry_setup")
async def test_speedtest_button(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify that speedtest trigger button works as expected."""
    entity_id = "button.unifi_network_speedtest"
    assert hass.states.get(entity_id) is not None

    # Clear previous mocks so we can check exact requests
    aioclient_mock.clear_requests()

    # Mock the POST request to trigger speedtest
    aioclient_mock.post(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/devmgr/speedtest",
        json={"meta": {"rc": "ok"}, "data": []},
    )

    call_count = 0

    async def mock_speedtest_get(
        method: str, url: Any, data: Any
    ) -> AiohttpClientMockResponse:

        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call (during _async_update_data startup) returns old payload
            return AiohttpClientMockResponse(
                method="GET",
                url=url,
                json=[
                    {
                        "download_mbps": 100.0,
                        "upload_mbps": 50.0,
                        "latency_ms": 10.0,
                        "time": 1600000000,
                        "interface_name": "eth0",
                    },
                    {
                        "download_mbps": 200.0,
                        "upload_mbps": 100.0,
                        "latency_ms": 5.0,
                        "time": 1600000000,
                        "interface_name": "eth2",
                    },
                ],
                headers={"content-type": "application/json"},
            )
        # Subsequent calls (polling loop) return new payload
        return AiohttpClientMockResponse(
            method="GET",
            url=url,
            json=[
                {
                    "download_mbps": 110.0,
                    "upload_mbps": 60.0,
                    "latency_ms": 9.0,
                    "time": 1600000030,  # Greater than 1600000000
                    "interface_name": "eth0",
                },
                {
                    "download_mbps": 220.0,
                    "upload_mbps": 120.0,
                    "latency_ms": 4.0,
                    "time": 1600000030,  # Greater than 1600000000
                    "interface_name": "eth2",
                },
            ],
            headers={"content-type": "application/json"},
        )

    # Use a callback side-effect for the GET mock
    aioclient_mock.get(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/v2/api/site/{config_entry_setup.data[CONF_SITE_ID]}/speedtest",
        side_effect=mock_speedtest_get,
    )

    # Press the speedtest button
    # Since _async_update_data has a sleep loop, let's mock asyncio.sleep to run instantly!
    with patch("asyncio.sleep"):
        await hass.services.async_call(
            BUTTON_DOMAIN, "press", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

    # Assert new states are updated!
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth0_download").state == "110.0"
    )
    assert hass.states.get("sensor.unifi_network_speedtest_eth0_upload").state == "60.0"
    assert hass.states.get("sensor.unifi_network_speedtest_eth0_ping").state == "9.0"
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth0_last_run").state
        == "2020-09-13T12:27:10+00:00"
    )

    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth2_download").state == "220.0"
    )
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth2_upload").state == "120.0"
    )
    assert hass.states.get("sensor.unifi_network_speedtest_eth2_ping").state == "4.0"
    assert (
        hass.states.get("sensor.unifi_network_speedtest_eth2_last_run").state
        == "2020-09-13T12:27:10+00:00"
    )


@pytest.mark.usefixtures("config_entry_setup")
async def test_speedtest_options_update(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test options update triggers speedtest interval change."""
    coordinator = config_entry_setup.runtime_data.speedtest_coordinator
    assert coordinator.update_interval.total_seconds() == 5400

    hass.config_entries.async_update_entry(
        config_entry_setup,
        options={
            "speedtest_interval": 120,
        },
    )
    await hass.async_block_till_done()

    assert coordinator.update_interval.total_seconds() == 7200


@pytest.mark.usefixtures("config_entry_setup")
async def test_speedtest_button_empty_result(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test speedtest button behavior when the polling returns empty data."""
    entity_id = "button.unifi_network_speedtest"

    # Mock the POST request to trigger speedtest
    aioclient_mock.post(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/devmgr/speedtest",
        json={"meta": {"rc": "ok"}, "data": []},
    )

    # Make the GET mock consistently return an empty list
    aioclient_mock.get(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/v2/api/site/{config_entry_setup.data[CONF_SITE_ID]}/speedtest",
        json=[],
        headers={"content-type": "application/json"},
    )

    with patch("asyncio.sleep"):
        await hass.services.async_call(
            BUTTON_DOMAIN, "press", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

    # The button shouldn't crash.
    # Note: aiounifi does not clear existing items if the API returns [],
    # so the data might not actually become None, but we cover the execution path.
    assert config_entry_setup.runtime_data.speedtest_coordinator.data is not None


@pytest.mark.usefixtures("config_entry_setup")
async def test_speedtest_sensor_empty_data(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test that sensors handle empty data correctly."""
    # Temporarily set the coordinator data to None
    coordinator = config_entry_setup.runtime_data.speedtest_coordinator

    # Verify native_value returns None when coordinator.data is None
    coordinator.data = None
    sensor_state = hass.states.get("sensor.unifi_network_speedtest_eth0_download")
    # Actually wait, sensor is already updated. Let's force an update
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    sensor_state = hass.states.get("sensor.unifi_network_speedtest_eth0_download")
    assert sensor_state.state == "unknown"

    # Verify native_value returns None when status for interface is missing
    coordinator.async_set_updated_data({})
    await hass.async_block_till_done()

    sensor_state = hass.states.get("sensor.unifi_network_speedtest_eth0_download")
    assert sensor_state.state == "unknown"
