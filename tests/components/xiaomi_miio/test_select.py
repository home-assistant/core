"""The tests for the xiaomi_miio select component."""

import logging

from arrow import utcnow
from miio.integrations.humidifier.zhimi.airhumidifier import LedBrightness
from miio.integrations.humidifier.zhimi.tests.test_airhumidifier import (
    DummyAirHumidifier,
)
import pytest

from homeassistant.components.asuswrt.router import KEY_COORDINATOR
from homeassistant.components.select.const import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.xiaomi_miio import (
    UPDATE_INTERVAL,
    _async_update_data_default,
)
from homeassistant.components.xiaomi_miio.const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MAC,
    DOMAIN,
    KEY_DEVICE,
    MODEL_AIRHUMIDIFIER_CA1,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.xiaomi_miio import TEST_MAC

_LOGGER = logging.getLogger(__name__)


async def setup_xiaomi_miio_select(hass: HomeAssistant, model, device) -> None:
    """Initialize setup xiaomi_miio select entity."""

    hass.data.setdefault(DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "0.0.0.0",
            CONF_TOKEN: "",
            CONF_MODEL: model,
            CONF_MAC: TEST_MAC,
        },
        unique_id="12345678",
    )
    config_entry.add_to_hass(hass)

    # Create update miio device and coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=config_entry.title,
        update_method=_async_update_data_default(hass, device),
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=UPDATE_INTERVAL,
    )
    hass.data[DOMAIN][config_entry.entry_id] = {
        KEY_DEVICE: device,
        KEY_COORDINATOR: coordinator,
    }

    # Trigger first data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "select")
    )

    await hass.async_block_till_done()


@pytest.fixture()
async def setup_xiaomi_miio_airhumidifier_select(hass: HomeAssistant):
    """Initialize setup xiaomi_miio airhumidifier select entity."""

    dummy_device = DummyAirHumidifier(MODEL_AIRHUMIDIFIER_CA1)
    await setup_xiaomi_miio_select(hass, MODEL_AIRHUMIDIFIER_CA1, dummy_device)
    return dummy_device


def test_setup_led_brightness_params(
    hass: HomeAssistant, setup_xiaomi_miio_airhumidifier_select
) -> None:
    """Test the initial parameters."""
    ptc_level_state = hass.states.get("select.mock_title_led_brightness")
    assert ptc_level_state
    assert ptc_level_state.state == "off"
    assert ptc_level_state.attributes.get(ATTR_OPTIONS) == ["bright", "dim", "off"]


async def test_select_led_brightness_option_bad_attr(
    hass: HomeAssistant, setup_xiaomi_miio_airhumidifier_select
) -> None:
    """Test selecting a different option with invalid option value."""
    state = hass.states.get("select.mock_title_led_brightness")
    assert state
    assert state.state == "off"

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "on", ATTR_ENTITY_ID: "select.mock_title_led_brightness"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get("select.mock_title_led_brightness")
    assert state
    assert state.state == "off"


async def test_select_led_brightness_option(
    hass: HomeAssistant, setup_xiaomi_miio_airhumidifier_select
) -> None:
    """Test selecting of a option."""
    state = hass.states.get("select.mock_title_led_brightness")
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "bright", ATTR_ENTITY_ID: "select.mock_title_led_brightness"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.mock_title_led_brightness")
    assert state
    assert state.state == "bright"


async def test_select_airhumidifier_coordinator_update(
    hass: HomeAssistant, setup_xiaomi_miio_airhumidifier_select
) -> None:
    """Test coordinator update of a option."""
    state = hass.states.get("select.mock_title_led_brightness")
    assert state
    assert state.state == "off"

    # emulate someone change state from device maybe used app
    setup_xiaomi_miio_airhumidifier_select.set_led_brightness(LedBrightness.Bright)

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("select.mock_title_led_brightness")
    assert state
    assert state.state == "bright"
