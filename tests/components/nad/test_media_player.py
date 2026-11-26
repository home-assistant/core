"""Test NAD source configuration and selection."""

from unittest.mock import patch

import probatio
import pytest

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.nad.media_player import SOURCE_DICT_SCHEMA
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_ID = "media_player.nad_receiver"


@pytest.mark.parametrize(
    "source",
    [1, 2, 12, "OPT 1", "OPT 2", "COAX 1", "DISC/MDC"],
)
def test_source_keys(source: int | str) -> None:
    """Preserve numeric keys and exact named source tokens."""
    assert SOURCE_DICT_SCHEMA({source: "Input"}) == {source: "Input"}


@pytest.mark.parametrize("source", [0, 13, "2", "12", "0", "13", " 2 ", "", " "])
def test_invalid_source_keys(source: int | str) -> None:
    """Reject out-of-range numbers and keys that cannot match numeric replies."""
    with pytest.raises(probatio.Invalid):
        SOURCE_DICT_SCHEMA({source: "Input"})


@pytest.mark.parametrize("connection", ["RS232", "Telnet"])
@pytest.mark.parametrize(
    ("source", "label"),
    [
        (2, "Numeric input"),
        ("OPT 1", "Optical 1"),
        ("OPT 2", "Optical 2"),
        ("COAX 1", "Coaxial 1"),
    ],
)
async def test_source_selection_and_update(
    hass: HomeAssistant, connection: str, source: int | str, label: str
) -> None:
    """Select and report sources from a mixed numeric and named mapping."""
    sources = {
        2: "Numeric input",
        "OPT 1": "Optical 1",
        "OPT 2": "Optical 2",
        "COAX 1": "Coaxial 1",
    }
    current_source: int | str | None = None

    def main_source(operator: str, value: int | str | None = None) -> int | str | None:
        nonlocal current_source
        if operator == "=":
            current_source = value
        return current_source

    with (
        patch("homeassistant.components.nad.media_player.NADReceiver") as serial,
        patch("homeassistant.components.nad.media_player.NADReceiverTelnet") as telnet,
    ):
        receiver = {"RS232": serial, "Telnet": telnet}[connection].return_value
        receiver.main_power.return_value = "On"
        receiver.main_mute.return_value = "Off"
        receiver.main_volume.return_value = -40
        receiver.main_source.side_effect = main_source

        assert await async_setup_component(
            hass,
            MEDIA_PLAYER_DOMAIN,
            {
                MEDIA_PLAYER_DOMAIN: {
                    "platform": "nad",
                    "type": connection,
                    "host": "receiver",
                    "sources": sources,
                }
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state.attributes[ATTR_INPUT_SOURCE_LIST] == sorted(sources.values())
        assert ATTR_INPUT_SOURCE not in state.attributes

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: label},
            blocking=True,
        )

    receiver.main_source.assert_any_call("=", source)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE] == label
