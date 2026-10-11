"""Test the BLE Battery Management System integration constants definition."""

from homeassistant.components.bms_ble.const import UPDATE_INTERVAL


async def test_critical_constants() -> None:
    """Test general constants are not altered for debugging."""

    assert (  # ensure that update interval is 30 seconds
        UPDATE_INTERVAL == 30
    ), "Update interval incorrect!"
