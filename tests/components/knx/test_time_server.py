"""Test KNX time server."""

import pytest

from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator

# Freeze time: 2026-1-29 11:02:03 UTC -> Europe/Vienna (UTC+1) = 12:02:03 Thursday
FREEZE_TIME = "2026-1-29 11:02:03"

# KNX Time DPT 10.001: Day of week + time
# 0x8C = 0b10001100 = Thursday (100) + 12 hours (01100)
# 0x02 = 2 minutes
# 0x03 = 3 seconds
RAW_TIME = (0x8C, 0x02, 0x03)

# KNX Date DPT 11.001
# 0x1D = 29th day
# 0x01 = January (month 1)
# 0x1A = 26 (2026 - 2000)
RAW_DATE = (0x1D, 0x01, 0x1A)

# KNX DateTime DPT 19.001: Year, Month, Day, Hour+DoW, Minutes, Seconds, Flags, Quality
# 0x7E = 126 (offset from 1900)
# 0x01 = January
# 0x1D = 29th day
# 0x8C = Thursday + 12 hours
# 0x02 = 2 minutes
# 0x03 = 3 seconds
# 0x20 = ignore working day flag, no DST
# 0xC0 = external sync, reliable source
RAW_DATETIME = (0x7E, 0x01, 0x1D, 0x8C, 0x02, 0x03, 0x20, 0xC0)


@pytest.mark.freeze_time(FREEZE_TIME)
@pytest.mark.parametrize(
    ("config", "expected_telegrams"),
    [
        (
            {"time": {"write": "1/1/1"}},
            {"1/1/1": RAW_TIME},
        ),
        (
            {"date": {"write": "2/2/2"}},
            {"2/2/2": RAW_DATE},
        ),
        (
            {"datetime": {"write": "3/3/3"}},
            {"3/3/3": RAW_DATETIME},
        ),
        (
            {"time": {"write": "1/1/1"}, "date": {"write": "2/2/2"}},
            {
                "1/1/1": RAW_TIME,
                "2/2/2": RAW_DATE,
            },
        ),
        (
            {"date": {"write": "2/2/2"}, "datetime": {"write": "3/3/3"}},
            {
                "2/2/2": RAW_DATE,
                "3/3/3": RAW_DATETIME,
            },
        ),
    ],
)
async def test_time_server_write_format(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    config: dict,
    expected_telegrams: dict[str, tuple],
) -> None:
    """Test time server writes each format when configured."""
    await hass.config.async_set_time_zone("Europe/Vienna")
    await knx.setup_integration({})
    client = await hass_ws_client(hass)

    # Get initial empty configuration
    await client.send_json_auto_id({"type": "knx/get_time_server_config"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == {}

    # Update time server config to enable format
    await client.send_json_auto_id(
        {"type": "knx/update_time_server_config", "config": config}
    )
    res = await client.receive_json()
    assert res["success"], res

    # Verify telegrams are written
    for address, expected_value in expected_telegrams.items():
        await knx.assert_write(address, expected_value)
    # Verify read responses work
    for address, expected_value in expected_telegrams.items():
        await knx.receive_read(address)
        await knx.assert_response(address, expected_value)


@pytest.mark.freeze_time(FREEZE_TIME)
async def test_time_server_load_from_config_store(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test time server is loaded correctly from config store."""
    await hass.config.async_set_time_zone("Europe/Vienna")
    await knx.setup_integration(
        {}, config_store_fixture="config_store_time_server.json"
    )
    # Verify all three formats are written on startup
    await knx.assert_write("1/1/1", RAW_TIME, ignore_order=True)
    await knx.assert_write("2/2/2", RAW_DATE, ignore_order=True)
    await knx.assert_write("3/3/3", RAW_DATETIME, ignore_order=True)

    client = await hass_ws_client(hass)
    # Verify configuration was loaded
    await client.send_json_auto_id({"type": "knx/get_time_server_config"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == {
        "time": {"write": "1/1/1"},
        "date": {"write": "2/2/2"},
        "datetime": {"write": "3/3/3"},
    }


@pytest.mark.parametrize(
    "invalid_config",
    [
        {"invalid": 1},
        {"time": {"state": "1/2/3"}},
        {"time": {"write": "not_an_address"}},
        {"date": {"passive": ["1/2/3"]}},
        {"datetime": {}},
        {"time": {"write": "1/2/3"}, "invalid_key": "value"},
    ],
)
async def test_time_server_invalid_config(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    invalid_config: dict,
) -> None:
    """Test invalid time server configuration is rejected."""
    await knx.setup_integration({})
    client = await hass_ws_client(hass)

    # Try to update with invalid configuration
    await client.send_json_auto_id(
        {"type": "knx/update_time_server_config", "config": invalid_config}
    )
    res = await client.receive_json()
    assert res["success"]  # uses custom error handling
    assert not res["result"]["success"]
    assert "errors" in res["result"]
