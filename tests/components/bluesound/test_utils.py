"""Test bluesound utils."""

from pyblu import PairedPlayer
import pytest

from homeassistant.components.bluesound.utils import id_to_paired_player


@pytest.mark.parametrize(
    ("player_id", "expected"),
    [
        pytest.param("1.1.1.1:11000", PairedPlayer("1.1.1.1", 11000), id="valid"),
        pytest.param("1.1.1.1", None, id="no_port"),
        pytest.param("1.1.1.1:port", None, id="non_numeric_port"),
    ],
)
def test_id_to_paired_player(player_id: str, expected: PairedPlayer | None) -> None:
    """Test converting an id to a paired player."""
    assert id_to_paired_player(player_id) == expected
