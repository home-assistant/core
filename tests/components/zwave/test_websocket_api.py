"""Test Z-Wave Websocket API."""
from homeassistant.bootstrap import async_setup_component
from homeassistant.components.zwave.const import (
    CONF_AUTOHEAL,
    CONF_NETWORK_KEY,
    CONF_POLLING_INTERVAL,
    CONF_USB_STICK_PATH,
)
from homeassistant.components.zwave.websocket_api import ID, TYPE


async def test_zwave_ws_api(hass, mock_openzwave, hass_ws_client):
    """Test Z-Wave websocket API."""

    await async_setup_component(
        hass,
        "zwave",
        {
            "zwave": {
                CONF_AUTOHEAL: False,
                CONF_USB_STICK_PATH: "/dev/zwave",
                CONF_POLLING_INTERVAL: 6000,
                CONF_NETWORK_KEY: "0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST",
            }
        },
    )

    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({ID: 5, TYPE: "zwave/get_config"})

    msg = await client.receive_json()
    result = msg["result"]

    assert result[CONF_USB_STICK_PATH] == "/dev/zwave"
    assert not result[CONF_AUTOHEAL]
    assert result[CONF_POLLING_INTERVAL] == 6000

    await client.send_json({ID: 6, TYPE: "zwave/get_migration_config"})
    msg = await client.receive_json()
    result = msg["result"]

    assert result[CONF_USB_STICK_PATH] == "/dev/zwave"
    assert (
        result[CONF_NETWORK_KEY]
        == "0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST, 0xTE, 0xST"
    )
