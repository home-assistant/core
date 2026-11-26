"""Tests for Xiaomi Miio switches (buzzer and led / led_light) with state assertions and updates."""

from unittest.mock import MagicMock, patch

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.xiaomi_miio import UPDATE_INTERVAL
from homeassistant.components.xiaomi_miio.const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRPURIFIER_V1,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


async def _assert_switch_states(
    hass: HomeAssistant,
    model: str,
    patch_target: str,
    light_attr: str,
) -> None:
    """Assert switch states and coordinator updates for a humidifier model."""

    mock_device = MagicMock()
    status = MagicMock()
    status.buzzer = False
    setattr(status, light_attr, True)
    mock_device.status.return_value = status

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[SWITCH_DOMAIN],
        ),
        patch(
            patch_target,
            return_value=mock_device,
        ),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="123456",
            title=f"test_humidifier_{model.rsplit('.', maxsplit=1)[-1]}",
            data={
                CONF_FLOW_TYPE: CONF_DEVICE,
                CONF_HOST: "192.168.1.100",
                CONF_TOKEN: "token",
                CONF_MODEL: model,
                CONF_MAC: TEST_MAC,
            },
        )

        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        switch_ids = hass.states.async_entity_ids(SWITCH_DOMAIN)
        buzzer_entity = next(
            entity_id for entity_id in switch_ids if "buzzer" in entity_id
        )
        light_entity = next(
            entity_id
            for entity_id in switch_ids
            if (light_attr in entity_id or "led" in entity_id)
        )

        state_buzzer = hass.states.get(buzzer_entity)
        state_light = hass.states.get(light_entity)
        assert state_buzzer is not None
        assert state_light is not None
        assert state_buzzer.state == "off"
        assert state_light.state == "on"

        status.buzzer = True
        setattr(status, light_attr, False)

        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

        state_buzzer_updated = hass.states.get(buzzer_entity)
        state_light_updated = hass.states.get(light_entity)
        assert state_buzzer_updated is not None
        assert state_light_updated is not None
        assert state_buzzer_updated.state == "on"
        assert state_light_updated.state == "off"


async def test_led_switches_mjjsq(hass: HomeAssistant) -> None:
    """Test led switch for MJJSQ humidifier."""
    await _assert_switch_states(
        hass,
        "deerma.humidifier.mjjsq",
        "homeassistant.components.xiaomi_miio.AirHumidifierMjjsq",
        "led",
    )


async def test_led_light_switches_jsq2w(hass: HomeAssistant) -> None:
    """Test led_light switch for JSQ2W humidifier."""
    await _assert_switch_states(
        hass,
        "deerma.humidifier.jsq2w",
        "homeassistant.components.xiaomi_miio.AirHumidifierJsqs",
        "led_light",
    )


async def test_dry_switch_ca4(hass: HomeAssistant) -> None:
    """Test dry switch for CA4 humidifier (miot)."""
    await _assert_switch_states(
        hass,
        MODEL_AIRHUMIDIFIER_CA4,
        "homeassistant.components.xiaomi_miio.AirHumidifierMiot",
        "dry",
    )


async def test_led_switch_airpurifier_v1(hass: HomeAssistant) -> None:
    """Test led switch for AirPurifier V1."""
    await _assert_switch_states(
        hass,
        MODEL_AIRPURIFIER_V1,
        "homeassistant.components.xiaomi_miio.AirPurifier",
        "led",
    )
