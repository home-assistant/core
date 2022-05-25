"""Test the Hardkernel hardware platform."""
import pytest

from homeassistant.components.hardkernel.const import DOMAIN
from homeassistant.components.hassio import DATA_OS_INFO
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockModule, mock_integration


async def test_hardware_info(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can get the board info."""
    mock_integration(hass, MockModule("hassio"))
    hass.data[DATA_OS_INFO] = {"board": "odroid-n2"}

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "hardware/info"})
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {
        "hardware": [
            {
                "board": {
                    "hassio_board_id": "odroid-n2",
                    "manufacturer": "hardkernel",
                    "model": "odroid-n2",
                    "revision": None,
                },
                "name": "Home Assistant Blue / Hardkernel Odroid-N2",
                "url": None,
            }
        ]
    }


@pytest.mark.parametrize("os_info", [None, {"board": None}, {"board": "other"}])
async def test_hardware_info_fail(hass: HomeAssistant, hass_ws_client, os_info) -> None:
    """Test async_info raises if os_info is not as expected."""
    mock_integration(hass, MockModule("hassio"))
    hass.data[DATA_OS_INFO] = os_info

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "hardware/info"})
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {"hardware": []}
