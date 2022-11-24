"""Test the spencer Assistant Yellow hardware platform."""
from unittest.mock import patch

import pytest

from spencerassistant.components.spencerassistant_yellow.const import DOMAIN
from spencerassistant.core import spencerAssistant

from tests.common import MockConfigEntry, MockModule, mock_integration


async def test_hardware_info(
    hass: spencerAssistant, hass_ws_client, addon_store_info
) -> None:
    """Test we can get the board info."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="spencer Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "spencerassistant.components.spencerassistant_yellow.get_os_info",
        return_value={"board": "yellow"},
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "spencerassistant.components.spencerassistant_yellow.hardware.get_os_info",
        return_value={"board": "yellow"},
    ):
        await client.send_json({"id": 1, "type": "hardware/info"})
        msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {
        "hardware": [
            {
                "board": {
                    "hassio_board_id": "yellow",
                    "manufacturer": "spencerassistant",
                    "model": "yellow",
                    "revision": None,
                },
                "config_entries": [config_entry.entry_id],
                "dongle": None,
                "name": "spencer Assistant Yellow",
                "url": None,
            }
        ]
    }


@pytest.mark.parametrize("os_info", [None, {"board": None}, {"board": "other"}])
async def test_hardware_info_fail(
    hass: spencerAssistant, hass_ws_client, os_info, addon_store_info
) -> None:
    """Test async_info raises if os_info is not as expected."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="spencer Assistant Yellow",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "spencerassistant.components.spencerassistant_yellow.get_os_info",
        return_value={"board": "yellow"},
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "spencerassistant.components.spencerassistant_yellow.hardware.get_os_info",
        return_value=os_info,
    ):
        await client.send_json({"id": 1, "type": "hardware/info"})
        msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {"hardware": []}
