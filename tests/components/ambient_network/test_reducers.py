"""Test the Ambient Weather Network reducers utilities."""

from homeassistant.components.ambient_network.reducers import Reducers


def test_reducers() -> None:
    """Test reducers."""

    assert Reducers.max([12.0, 11.0, 5.0]) == 12.0
    assert Reducers.max([12.0, 11.0]) == 12.0
    assert Reducers.mean([12.0, 10.0, 20.0]) == 11.0
    assert Reducers.mean([12.0, 10.0]) == 11.0
