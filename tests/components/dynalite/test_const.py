"""Check that the consts in the component / HA are the same as in the library."""
from dynalite_devices_lib import const as dyn_const

from homeassistant.components import dynalite
import homeassistant.const as ha_const


def test_consts():
    """Verify that the consts defined in HA and the component are the same as the ones in the library."""
    assert ha_const.CONF_HOST == dyn_const.CONF_HOST
    assert dynalite.CONF_ACTIVE == dyn_const.CONF_ACTIVE
    assert dynalite.CONF_ACTIVE_INIT == dyn_const.CONF_ACTIVE_INIT
    assert dynalite.CONF_ACTIVE_OFF == dyn_const.CONF_ACTIVE_OFF
    assert dynalite.CONF_ACTIVE_ON == dyn_const.CONF_ACTIVE_ON
    assert dynalite.CONF_AREA == dyn_const.CONF_AREA
    assert dynalite.CONF_AUTO_DISCOVER == dyn_const.CONF_AUTO_DISCOVER
    assert dynalite.CONF_CHANNEL == dyn_const.CONF_CHANNEL
    assert dynalite.CONF_CHANNEL_COVER == dyn_const.CONF_CHANNEL_COVER
    assert dynalite.CONF_CHANNEL_TYPE == dyn_const.CONF_CHANNEL_TYPE
    assert dynalite.CONF_CLOSE_PRESET == dyn_const.CONF_CLOSE_PRESET
    assert dynalite.CONF_DEFAULT == dyn_const.CONF_DEFAULT
    assert dynalite.CONF_DEVICE_CLASS == dyn_const.CONF_DEVICE_CLASS
    assert dynalite.CONF_DURATION == dyn_const.CONF_DURATION
    assert dynalite.CONF_FADE == dyn_const.CONF_FADE
    assert dynalite.CONF_NAME == dyn_const.CONF_NAME
    assert dynalite.CONF_NO_DEFAULT == dyn_const.CONF_NO_DEFAULT
    assert dynalite.CONF_OPEN_PRESET == dyn_const.CONF_OPEN_PRESET
    assert dynalite.CONF_POLL_TIMER == dyn_const.CONF_POLL_TIMER
    assert dynalite.CONF_PORT == dyn_const.CONF_PORT
    assert dynalite.CONF_PRESET == dyn_const.CONF_PRESET
    assert dynalite.CONF_ROOM_OFF == dyn_const.CONF_ROOM_OFF
    assert dynalite.CONF_ROOM_ON == dyn_const.CONF_ROOM_ON
    assert dynalite.CONF_STOP_PRESET == dyn_const.CONF_STOP_PRESET
    assert dynalite.CONF_TEMPLATE == dyn_const.CONF_TEMPLATE
    assert dynalite.CONF_TILT_TIME == dyn_const.CONF_TILT_TIME
    assert dynalite.CONF_TRIGGER == dyn_const.CONF_TRIGGER
    assert dynalite.DEFAULT_CHANNEL_TYPE == dyn_const.DEFAULT_CHANNEL_TYPE
    assert dynalite.DEFAULT_NAME == dyn_const.DEFAULT_NAME
    assert dynalite.DEFAULT_PORT == dyn_const.DEFAULT_PORT
    # check that all the templates have the same parameters
    for template in dynalite.DEFAULT_TEMPLATES:
        assert dynalite.DEFAULT_TEMPLATES[template] == list(
            dyn_const.DEFAULT_TEMPLATES[template]
        )
