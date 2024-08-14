"""Test the Geniushub config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.geniushub import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def mock_cloud_all(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock all setup requests."""
    zones = load_json_object_fixture("zones_cloud_test_data.json", DOMAIN)
    devices = load_json_object_fixture("devices_cloud_test_data.json", DOMAIN)
    aioclient_mock.get(
        "https://my.geniushub.co.uk/v1/version",
        json={
            "hubSoftwareVersion": "6.3.10",
            "earliestCompatibleAPI": "my.geniushub.co.uk/v1",
            "latestCompatibleAPI": "my.geniushub.co.uk/v1",
        },
    )
    aioclient_mock.get("https://my.geniushub.co.uk/v1/zones", json=zones)
    aioclient_mock.get("https://my.geniushub.co.uk/v1/devices", json=devices)
    aioclient_mock.get("https://my.geniushub.co.uk/v1/issues", json=[])


@pytest.fixture(autouse=True)
def mock_cloud_single_zone_with_switch(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock all setup requests."""
    zones = load_json_object_fixture("single_zone_local_test_data.json", DOMAIN)
    devices = load_json_object_fixture("single_switch_local_test_data.json", DOMAIN)
    switch_on = load_json_object_fixture("switch_on_local_test_data.json", DOMAIN)
    switch_off = load_json_object_fixture("switch_off_local_test_data.json", DOMAIN)
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/auth/release",
        json=({"data": {"UID": "aa:bb:cc:dd:ee:ff", "release": "10.0"}}),
    )
    aioclient_mock.get("http://10.0.0.130:1223/v3/zones", json=zones)
    aioclient_mock.get(
        "http://10.0.0.130:1223/v3/data_manager",
        json=devices,
    )
    aioclient_mock.patch(
        "http://10.0.0.130:1223/v3/zone/32",
        json=switch_on,
    )
    aioclient_mock.patch(
        "http://10.0.0.131:1223/v3/zone/32",
        json=switch_off,
    )


async def test_cloud_all_sensors(
    hass: HomeAssistant,
    mock_cloud_config_entry: AsyncMock,
    mock_cloud_all: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test full cloud flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_api"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TOKEN: "abcdef",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Genius hub"
    assert result["data"] == {
        CONF_TOKEN: "abcdef",
    }


async def xtest_cloud_single_zone_and_switch(
    hass: HomeAssistant,
    mock_cloud_config_entry: AsyncMock,
    mock_cloud_single_zone_with_switch: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test full local flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.130",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    test_entity_id = "switch.study_socket"
    switch = hass.states.get(test_entity_id)
    assert switch.state == "off"

    # call the HA turn_on service
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    # The state should change but will not change until the next refresh
    # How do I force a refresh?
    await hass.async_block_till_done()
    assert switch.state == "off"

    # now call the HA turn_off service
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": test_entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert switch.state == "off"
