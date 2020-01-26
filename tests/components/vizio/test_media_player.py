"""Tests for Vizio config flow."""
import logging

from asynctest import patch
from pyvizio.const import (
    DEVICE_CLASS_SPEAKER as VIZIO_DEVICE_CLASS_SPEAKER,
    DEVICE_CLASS_TV as VIZIO_DEVICE_CLASS_TV,
)
from pyvizio.vizio import MAX_VOLUME

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DEVICE_CLASS_SPEAKER,
    DEVICE_CLASS_TV,
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.components.vizio.const import DOMAIN
from homeassistant.components.vizio.media_player import async_setup_entry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

NAME = "Vizio"
HOST = "192.168.1.1:9000"
ACCESS_TOKEN = "deadbeef"
VOLUME_STEP = 2
TIMEOUT = 3
UNIQUE_ID = "testid"

CURRENT_INPUT = "HDMI"
INPUT_LIST = ["HDMI", "USB", "Bluetooth", "AUX"]

TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
}

ENTITY_ID = f"{MP_DOMAIN.lower()}.{NAME.lower()}"

SPEAKER_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER,
}

SPEAKER_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN, data=SPEAKER_CONFIG, unique_id=UNIQUE_ID
)
TV_CONFIG_ENTRY = MockConfigEntry(domain=DOMAIN, data=TV_CONFIG, unique_id=UNIQUE_ID)


class MockInput:
    """Mock Vizio device input."""

    def __init__(self, name):
        """Initialize mock Vizio device input."""
        self.meta_name = name
        self.name = name


def get_mock_inputs(input_list):
    """Return list of MockInput."""
    return [MockInput(input) for input in input_list]


async def _test_vizio_init(
    hass: HomeAssistantType,
    config: dict,
    vizio_device_class: str,
    ha_device_class: str,
    vizio_power_state: bool,
    ha_power_state: str,
) -> None:
    """Test initialization of Vizio Device entity with device class `speaker`."""

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.can_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_unique_id",
        return_value=UNIQUE_ID,
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_current_volume",
        return_value=int(MAX_VOLUME[vizio_device_class] / 2),
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_current_input",
        return_value=MockInput(CURRENT_INPUT),
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_inputs",
        return_value=get_mock_inputs(INPUT_LIST),
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_power_state",
        return_value=vizio_power_state,
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()

        attr = hass.states.get(ENTITY_ID).attributes
        assert attr["friendly_name"] == NAME
        assert attr["device_class"] == ha_device_class

        assert hass.states.get(ENTITY_ID).state == ha_power_state
        if ha_power_state == STATE_ON:
            assert attr["source_list"] == INPUT_LIST
            assert attr["source"] == CURRENT_INPUT
            assert (
                attr["volume_level"]
                == float(int(MAX_VOLUME[vizio_device_class] / 2))
                / MAX_VOLUME[vizio_device_class]
            )


async def test_vizio_speaker_on(hass: HomeAssistantType) -> None:
    """Test for Vizio Speaker entity when on."""
    await _test_vizio_init(
        hass,
        SPEAKER_CONFIG,
        VIZIO_DEVICE_CLASS_SPEAKER,
        DEVICE_CLASS_SPEAKER,
        True,
        STATE_ON,
    )


async def test_vizio_speaker_off(hass: HomeAssistantType) -> None:
    """Test for Vizio Speaker entity when off."""
    await _test_vizio_init(
        hass,
        SPEAKER_CONFIG,
        VIZIO_DEVICE_CLASS_SPEAKER,
        DEVICE_CLASS_SPEAKER,
        False,
        STATE_OFF,
    )


async def test_vizio_speaker_unavailable(hass: HomeAssistantType) -> None:
    """Test for Vizio Speaker entity when unavailable."""
    await _test_vizio_init(
        hass,
        SPEAKER_CONFIG,
        VIZIO_DEVICE_CLASS_SPEAKER,
        DEVICE_CLASS_SPEAKER,
        None,
        STATE_UNAVAILABLE,
    )


async def test_vizio_init_tv_on(hass: HomeAssistantType) -> None:
    """Test for Vizio TV entity when on."""
    await _test_vizio_init(
        hass, TV_CONFIG, VIZIO_DEVICE_CLASS_TV, DEVICE_CLASS_TV, True, STATE_ON
    )


async def test_vizio_init_tv_off(hass: HomeAssistantType) -> None:
    """Test for Vizio TV entity when off."""
    await _test_vizio_init(
        hass, TV_CONFIG, VIZIO_DEVICE_CLASS_TV, DEVICE_CLASS_TV, False, STATE_OFF
    )


async def test_vizio_init_tv_unavailable(hass: HomeAssistantType) -> None:
    """Test for Vizio TV entity when unavailable."""
    await _test_vizio_init(
        hass, TV_CONFIG, VIZIO_DEVICE_CLASS_TV, DEVICE_CLASS_TV, None, STATE_UNAVAILABLE
    )


async def test_setup_failure(hass: HomeAssistantType) -> None:
    """Test media player entity setup failure."""
    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.can_connect",
        return_value=False,
    ):
        try:
            await async_setup_entry(hass, SPEAKER_CONFIG_ENTRY, None)
        except Exception as e:
            assert isinstance(e, PlatformNotReady)

        try:
            await async_setup_entry(hass, TV_CONFIG_ENTRY, None)
        except Exception as e:
            assert isinstance(e, PlatformNotReady)


async def test_services(hass: HomeAssistantType) -> None:
    """Test media player entity services."""
    await _test_vizio_init(
        hass, TV_CONFIG, VIZIO_DEVICE_CLASS_TV, DEVICE_CLASS_TV, True, STATE_ON,
    )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.pow_on"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_TURN_ON,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.pow_off"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_TURN_OFF,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.mute_on"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.mute_off"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.input_switch"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "USB"},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.vol_up"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_UP,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 1},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.vol_down"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_DOWN,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.ch_up"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    with patch("homeassistant.components.vizio.media_player.VizioAsync.ch_down"):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
