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
    hass: HomeAssistantType,
    config_entry: MockConfigEntry,
    vizio_device_class: str,
    ha_device_class: str,
    vizio_power_state: bool,
    ha_power_state: str,
) -> None:
    """Test initialization of Vizio Device entity with device class `speaker`."""

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
    await _test_init(
        hass,
        MockConfigEntry(domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID),
        VIZIO_DEVICE_CLASS_SPEAKER,
        DEVICE_CLASS_SPEAKER,
        True,
        STATE_ON,
    )


async def test_speaker_off(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio Speaker entity when off."""
    await _test_init(
        hass,
        MockConfigEntry(domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID),
        VIZIO_DEVICE_CLASS_SPEAKER,
        DEVICE_CLASS_SPEAKER,
        False,
        STATE_OFF,
    )


async def test_speaker_unavailable(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio Speaker entity when unavailable."""
    await _test_init(
        hass,
        MockConfigEntry(domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID),
        VIZIO_DEVICE_CLASS_SPEAKER,
        DEVICE_CLASS_SPEAKER,
        None,
        STATE_UNAVAILABLE,
    )


async def test_init_tv_on(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio TV entity when on."""
    await _test_init(
        hass,
        MockConfigEntry(
            domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
        ),
        VIZIO_DEVICE_CLASS_TV,
        DEVICE_CLASS_TV,
        True,
        STATE_ON,
    )


async def test_init_tv_off(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio TV entity when off."""
    await _test_init(
        hass,
        MockConfigEntry(
            domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
        ),
        VIZIO_DEVICE_CLASS_TV,
        DEVICE_CLASS_TV,
        False,
        STATE_OFF,
    )


async def test_init_tv_unavailable(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for Vizio TV entity when unavailable."""
    await _test_init(
        hass,
        MockConfigEntry(
            domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
        ),
        VIZIO_DEVICE_CLASS_TV,
        DEVICE_CLASS_TV,
        None,
        STATE_UNAVAILABLE,
    )


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


async def test_services(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test media player entity services."""
    await _test_init(
        hass,
        MockConfigEntry(
            domain=DOMAIN, data=MOCK_USER_VALID_TV_CONFIG, unique_id=UNIQUE_ID
        ),
        VIZIO_DEVICE_CLASS_TV,
        DEVICE_CLASS_TV,
        True,
        STATE_ON,
    )

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.pow_on"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_TURN_ON,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        assert service_call.call_count == 1

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.pow_off"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_TURN_OFF,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        assert service_call.call_count == 1

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.mute_on"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )
        assert service_call.call_count == 1

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.mute_off"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
            blocking=True,
        )
        assert service_call.call_count == 1

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.input_switch"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "USB"},
            blocking=True,
        )
        assert service_call.call_count == 1

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.vol_up"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_UP,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        assert service_call.call_count == 1

        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 1},
            blocking=True,
        )
        assert service_call.call_count == 2

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.vol_down"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_DOWN,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        assert service_call.call_count == 1

        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0},
            blocking=True,
        )
        assert service_call.call_count == 2

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.ch_up"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        assert service_call.call_count == 1

    with patch(
        "homeassistant.components.vizio.media_player.VizioAsync.ch_down"
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            service_data={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        assert service_call.call_count == 1


async def test_options_update(
    hass: HomeAssistantType, vizio_connect: pytest.fixture, vizio_update: pytest.fixture
) -> None:
    """Test for when config entry update event fires."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SPEAKER_CONFIG, unique_id=UNIQUE_ID
    )
    await _test_init(
        hass,
        config_entry,
        VIZIO_DEVICE_CLASS_SPEAKER,
        DEVICE_CLASS_SPEAKER,
        True,
        STATE_ON,
    )

    updated_options = {CONF_VOLUME_STEP: VOLUME_STEP}
    new_options = config_entry.options.copy()
    new_options.update(updated_options)
    hass.config_entries.async_update_entry(
        entry=config_entry, options=new_options,
    )
    assert config_entry.options == updated_options
