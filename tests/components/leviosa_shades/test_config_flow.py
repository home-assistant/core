"""Test the Leviosa Motor Shades Zone config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.leviosa_shades.const import (
    BLIND_GROUPS,
    DEVICE_FW_V,
    DEVICE_MAC,
    DOMAIN,
    GROUP1_NAME,
    GROUP2_NAME,
    GROUP3_NAME,
    GROUP4_NAME,
)
from homeassistant.const import CONF_HOST, CONF_NAME

TEST_HOST1 = "1.2.3.4"
TEST_HOST2 = "5.6.7.8"
TEST_MAC1 = "40f5205b658c"
TEST_MAC2 = "40f5205b6687"

TEST_ZONE_FW = "8.3"
TEST_ZONE_FW_ALT = "0.0.0"

TEST_DISCOVERY_0 = {}
TEST_DISCOVERY_1 = {"uid:6bf25702-1d6a-4c7b-b949-40f5205b658c": TEST_HOST1}
TEST_DISCOVERY_2 = {
    "uid:6bf25702-1d6a-4c7b-b949-40f5205b658c": TEST_HOST1,
    "uid:6bf25702-1d6a-4c7b-b949-40f5205b6687": TEST_HOST2,
}

TEST_USER_INPUT_1 = {
    CONF_NAME: "Zone 1",
    GROUP1_NAME: "Z1 Group 1",
    GROUP2_NAME: "Z1 Group 2",
    GROUP3_NAME: "Z1 Group 3",
    GROUP4_NAME: "Z1 Group 4",
}
TEST_USER_INPUT_2 = {
    CONF_NAME: "Zone 2",
    GROUP1_NAME: "Z2 Group 1",
    GROUP2_NAME: "Z2 Group 2",
    GROUP3_NAME: "Z2 Group 3",
    GROUP4_NAME: "Z2 Group 4",
}


@pytest.fixture(name="leviosa_shades_connect", autouse=True)
def leviosa_shades_connect_fixture():
    """Mock motion blinds connection and entry setup."""
    with patch(
        "homeassistant.components.leviosa_shades.config_flow.discover_leviosa_zones",
        return_value=TEST_DISCOVERY_1,
    ), patch(
        "homeassistant.components.leviosa_shades.async_setup_entry", return_value=True
    ):
        yield


async def test_config_flow_one_zone_success(hass):
    """Successful flow initiated by the user, one Zone discovered."""
    with patch(
        "homeassistant.components.leviosa_shades.config_flow.discover_leviosa_zones",
        return_value=TEST_DISCOVERY_1,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.leviosa_shades.config_flow.validate_zone",
        return_value=TEST_ZONE_FW,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT_1
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_USER_INPUT_1[CONF_NAME]
    assert result["data"] == {
        CONF_HOST: TEST_HOST1,
        DEVICE_FW_V: TEST_ZONE_FW,
        DEVICE_MAC: TEST_MAC1,
        BLIND_GROUPS: [
            "All Zone 1",
            "Z1 Group 1",
            "Z1 Group 2",
            "Z1 Group 3",
            "Z1 Group 4",
        ],
    }

    with patch(
        "homeassistant.components.leviosa_shades.config_flow.discover_leviosa_zones",
        return_value=TEST_DISCOVERY_1,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "abort"


async def test_config_flow_two_zone_success(hass):
    """Successful flow initiated by the user, two Zones discovered, one selected."""
    with patch(
        "homeassistant.components.leviosa_shades.config_flow.discover_leviosa_zones",
        return_value=TEST_DISCOVERY_2,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "select"
    assert list(result["data_schema"].schema["select_ip"].container) == [
        TEST_HOST1,
        TEST_HOST2,
    ]
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"select_ip": TEST_HOST1},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.leviosa_shades.config_flow.validate_zone",
        return_value=TEST_ZONE_FW,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT_1
        )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_USER_INPUT_1[CONF_NAME]
    assert result["data"] == {
        CONF_HOST: TEST_HOST1,
        DEVICE_FW_V: TEST_ZONE_FW,
        DEVICE_MAC: TEST_MAC1,
        BLIND_GROUPS: [
            "All Zone 1",
            "Z1 Group 1",
            "Z1 Group 2",
            "Z1 Group 3",
            "Z1 Group 4",
        ],
    }


async def test_config_flow_no_zone_abort(hass):
    """Flow initiated by user, no Zones discovered."""
    with patch(
        "homeassistant.components.leviosa_shades.config_flow.discover_leviosa_zones",
        return_value=TEST_DISCOVERY_0,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "abort"
    assert result["reason"] == "no_new_devs"
