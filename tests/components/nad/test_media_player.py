"""Test NAD source configuration and selection."""

from unittest.mock import patch

import probatio
import pytest

from homeassistant.components.nad.media_player import (
    NAD,
    PLATFORM_SCHEMA,
    SOURCE_DICT_SCHEMA,
)


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
def test_source_selection_and_update(
    connection: str, source: int | str, label: str
) -> None:
    """Select and report sources from a mixed numeric and named mapping."""
    sources = {
        2: "Numeric input",
        "OPT 1": "Optical 1",
        "OPT 2": "Optical 2",
        "COAX 1": "Coaxial 1",
    }
    config = PLATFORM_SCHEMA(
        {"platform": "nad", "type": connection, "host": "receiver", "sources": sources}
    )
    with (
        patch("homeassistant.components.nad.media_player.NADReceiver") as serial,
        patch("homeassistant.components.nad.media_player.NADReceiverTelnet") as telnet,
    ):
        receiver = {"RS232": serial, "Telnet": telnet}[connection].return_value
        receiver.main_power.return_value = "On"
        receiver.main_mute.return_value = "Off"
        receiver.main_volume.return_value = -40
        receiver.main_source.return_value = source
        entity = NAD(config)

        assert entity.source_list == sorted(sources.values())
        entity.select_source(label)
        receiver.main_source.assert_called_once_with("=", source)

        entity.update()
        receiver.main_source.assert_called_with("?")
        assert entity.source == label
