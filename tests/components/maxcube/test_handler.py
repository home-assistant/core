"""Tests for MacCube handler."""
import asyncio
from socket import timeout

from homeassistant.components.maxcube import MaxCubeHandle

from tests.common import patch


async def test_handler_update(cube):
    """Test handler updates."""
    h = MaxCubeHandle(cube, 2)

    # No update after init
    assert h.update() is None
    assert 0 == cube.update.call_count

    # 2s not passed, no update
    await asyncio.sleep(1)
    assert h.update() is None
    assert 0 == cube.update.call_count
    cube.update.assert_not_called()

    # 2s passed, fist update
    await asyncio.sleep(1)
    assert h.update() is None
    assert 1 == cube.update.call_count

    # 1s passed after last update, no update
    await asyncio.sleep(1)
    assert h.update() is None
    assert 1 == cube.update.call_count

    # 2s passed after last update, second update
    await asyncio.sleep(1)
    assert h.update() is None
    assert 2 == cube.update.call_count

    # next update will have connection problem
    await asyncio.sleep(2)
    with patch.object(cube, "update", side_effect=timeout()):
        assert h.update() is False
