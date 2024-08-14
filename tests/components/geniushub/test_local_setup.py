"""Test the Geniushub config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.geniushub import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def mock_local_all(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock all setup requests."""
    zones = load_json_object_fixture("zones_local_test_data.json", DOMAIN)
    devices = load_json_object_fixture("devices_local_test_data.json", DOMAIN)
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


@pytest.fixture(autouse=True)
def mock_local_single_zone_with_switch(aioclient_mock: AiohttpClientMocker) -> None:
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


async def test_local_all_sensors(
    hass: HomeAssistant,
    mock_local_config_entry: AsyncMock,
    mock_local_all: AsyncMock,
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

    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


async def test_local_single_zone_and_switch(
    hass: HomeAssistant,
    mock_local_config_entry: AsyncMock,
    mock_local_single_zone_with_switch: AsyncMock,
    # entity_registry: er.EntityRegistry,
) -> None:
    """Test full local flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "local_api"},
    )

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
