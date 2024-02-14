"""Test the Hardkernel hardware platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.hardkernel.const import DOMAIN
from homeassistant.components.hassio import DOMAIN as HASSIO_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.typing import WebSocketGenerator


async def test_hardware_info(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can get the board info."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Hardkernel",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.hardkernel.get_os_info",
        return_value={"board": "odroid-n2"},
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.hardkernel.hardware.get_os_info",
        return_value={"board": "odroid-n2"},
    ):
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
                "config_entries": [config_entry.entry_id],
                "dongle": None,
                "name": "Home Assistant Blue / Hardkernel ODROID-N2/N2+",
                "url": None,
            }
        ]
    }


@pytest.mark.parametrize("os_info", [None, {"board": None}, {"board": "other"}])
async def test_hardware_info_fail(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, os_info
) -> None:
    """Test async_info raises if os_info is not as expected."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Hardkernel",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.hardkernel.get_os_info",
        return_value={"board": "odroid-n2"},
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.hardkernel.hardware.get_os_info",
        return_value=os_info,
    ):
        await client.send_json({"id": 1, "type": "hardware/info"})
        msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {"hardware": []}
