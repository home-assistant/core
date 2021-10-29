"""Test Evil Genius Labs light."""
import pytest


@pytest.mark.parametrize("platforms", [("light",)])
async def test_works(hass, setup_evil_genius_labs):
    """Test it works."""
    state = hass.states.get("light.fibonacci256_23d4")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 128
