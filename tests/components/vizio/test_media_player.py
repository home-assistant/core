"""Tests for Vizio config flow."""
from asynctest import patch
import pytest
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
from homeassistant.components.vizio.const import CONF_VOLUME_STEP, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CURRENT_INPUT,
    ENTITY_ID,
    INPUT_LIST,
    MOCK_SPEAKER_CONFIG,
    MOCK_USER_VALID_TV_CONFIG,
    NAME,
    UNIQUE_ID,
    VOLUME_STEP,
)

from tests.common import MockConfigEntry


async def _test_init(
    hass: HomeAssistantType, ha_device_class: str, vizio_power_state: bool,
) -> None:
    """Test initialization of generic Vizio Device entity."""
    if vizio_power_state:
        ha_power_state = STATE_ON
    elif vizio_power_state is False:
        ha_power_state = STATE_OFF
    else:
        ha_power_state = STATE_UNAVAILABLE

    if ha_device_class == DEVICE_CLASS_SPEAKER:
        vizio_device_class = VIZIO_DEVICE_CLASS_SPEAKER
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID
        )
    else:
        vizio_device_class = VIZIO_DEVICE_CLASS_TV
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
        )

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_current_volume",
        return_value=int(MAX_VOLUME[vizio_device_class] / 2),
    ), patch(
        "homeassistant.components.vizio.media_player.VizioAsync.get_power_state",
        return_value=vizio_power_state,
    ):
        await hass.config_entries.async_add(config_entry)
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


async def test_speaker_on(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio Speaker entity when on."""
    await _test_init(hass, DEVICE_CLASS_SPEAKER, True)


async def test_speaker_off(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio Speaker entity when off."""
    await _test_init(hass, DEVICE_CLASS_SPEAKER, False)


async def test_speaker_unavailable(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio Speaker entity when unavailable."""
    await _test_init(hass, DEVICE_CLASS_SPEAKER, None)


async def test_init_tv_on(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio TV entity when on."""
    await _test_init(hass, DEVICE_CLASS_TV, True)


async def test_init_tv_off(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio TV entity when off."""
    await _test_init(hass, DEVICE_CLASS_TV, False)


async def test_init_tv_unavailable(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio TV entity when unavailable."""
    await _test_init(hass, DEVICE_CLASS_TV, None)


async def test_setup_failure_speaker(
    hass: HomeAssistantType, vizio_connect: pytest.fixture
) -> None:
    """Test speaker entity setup failure."""
    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.can_connect",
        return_value=False,
    ):
        await hass.config_entries.async_add(
            MockConfigEntry(
                domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID
            )
        )
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 0


async def test_setup_failure_tv(
    hass: HomeAssistantType, vizio_connect: pytest.fixture
) -> None:
    """Test TV entity setup failure."""
    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.can_connect",
        return_value=False,
    ):
        await hass.config_entries.async_add(
            MockConfigEntry(
                domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
            )
        )
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids(MP_DOMAIN)) == 0


async def _test_service(
    hass: HomeAssistantType,
    vizio_func_name: str,
    ha_service_name: str,
    additional_service_data: dict = None,
):
    """Test a media player entity service."""
    service_data = {ATTR_ENTITY_ID: ENTITY_ID}
    if additional_service_data:
        service_data.update(additional_service_data)

    with patch(
        f"homeassistant.components.vizio.media_player.VizioAsync.{vizio_func_name}"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN, ha_service_name, service_data=service_data, blocking=True,
        )
        assert service_call.call_count == 1


async def test_services(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test media player entity services."""
    await _test_init(hass, DEVICE_CLASS_TV, True)

    await _test_service(hass, "pow_on", SERVICE_TURN_ON)
    await _test_service(hass, "pow_off", SERVICE_TURN_OFF)
    await _test_service(
        hass, "mute_on", SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}
    )
    await _test_service(
        hass, "mute_off", SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}
    )
    await _test_service(
        hass, "input_switch", SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "USB"}
    )
    await _test_service(hass, "vol_up", SERVICE_VOLUME_UP)
    await _test_service(hass, "vol_down", SERVICE_VOLUME_DOWN)
    await _test_service(
        hass, "vol_up", SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 1}
    )
    await _test_service(
        hass, "vol_down", SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0}
    )
    await _test_service(hass, "ch_up", SERVICE_MEDIA_NEXT_TRACK)
    await _test_service(hass, "ch_down", SERVICE_MEDIA_PREVIOUS_TRACK)


async def test_options_update(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for when config entry update event fires."""
    await _test_init(hass, DEVICE_CLASS_SPEAKER, True)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.options
    new_options = config_entry.options.copy()
    updated_options = {CONF_VOLUME_STEP: VOLUME_STEP}
    new_options.update(updated_options)
    hass.config_entries.async_update_entry(
        entry=config_entry, options=new_options,
    )
    assert config_entry.options == updated_options
