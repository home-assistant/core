"""Common code for PG LAB Electronics tests."""

import json

from homeassistant.core import HomeAssistant

from tests.common import async_fire_mqtt_message


def get_device_discovery_payload(
    number_of_shutters: int,
    number_of_boards: int,
    device_name: str = "test",
) -> dict[str, any]:
    """Return the device discovery payload."""

    # be sure the number of shutters and boards are in the correct range
    assert 0 <= number_of_boards <= 8
    assert 0 <= number_of_shutters <= (number_of_boards * 4)

    # define the number of E-RELAY boards connected to E-BOARD
    boards = "1" * number_of_boards + "0" * (8 - number_of_boards)

    return {
        "ip": "192.168.1.16",
        "mac": "80:34:28:1B:18:5A",
        "name": device_name,
        "hw": "1.0.7",
        "fw": "1.0.0",
        "type": "E-BOARD",
        "id": "E-BOARD-DD53AC85",
        "manufacturer": "PG LAB Electronics",
        "params": {"shutters": number_of_shutters, "boards": boards},
    }


async def send_discovery_message(
    hass: HomeAssistant,
    payload: dict[str, any] | None,
) -> None:
    """Send the discovery message to make E-BOARD device discoverable."""

    topic = "pglab/discovery/E-BOARD-DD53AC85/config"

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload if payload is not None else ""),
    )
    await hass.async_block_till_done()
