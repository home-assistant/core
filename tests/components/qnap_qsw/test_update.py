"""The sensor tests for the QNAP QSW platform."""

from aioqsw.const import API_RESULT, API_VERSION

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from .util import FIRMWARE_INFO_MOCK, FIRMWARE_UPDATE_CHECK_MOCK, async_init_integration


async def test_qnap_qsw_update(hass: HomeAssistant) -> None:
    """Test creation of update entities."""

    await async_init_integration(hass)

    update = hass.states.get("update.qsw_m408_4c_firmware_update")
    assert update is not None
    assert update.state == STATE_OFF
    assert (
        update.attributes.get("installed_version")
        == FIRMWARE_INFO_MOCK[API_RESULT][API_VERSION]
    )
    assert (
        update.attributes.get("latest_version")
        == FIRMWARE_UPDATE_CHECK_MOCK[API_RESULT][API_VERSION]
    )
