"""The tests for the xiaomi_miio select component."""

from unittest.mock import MagicMock, patch

from arrow import utcnow
from miio.integrations.airpurifier.dmaker.airfresh_t2017 import (
    DisplayOrientation,
    PtcLevel,
)
from miio.integrations.airpurifier.zhimi.airpurifier_miot import LedBrightness
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.xiaomi_miio import UPDATE_INTERVAL
from homeassistant.components.xiaomi_miio.const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    MODEL_AIRFRESH_T2017,
    MODEL_AIRPURIFIER_4,
    MODEL_AIRPURIFIER_4_PRO,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
async def setup_test(hass: HomeAssistant):
    """Initialize test xiaomi_miio for select entity."""

    mock_airfresh = MagicMock()
    mock_airfresh.status().display_orientation = DisplayOrientation.Portrait
    mock_airfresh.status().ptc_level = PtcLevel.Low

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[
                Platform.SELECT,
            ],
        ),
        patch(
            "homeassistant.components.xiaomi_miio.AirFreshT2017"
        ) as mock_airfresh_cls,
    ):
        mock_airfresh_cls.return_value = mock_airfresh
        yield mock_airfresh


async def test_select_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""

    entity_name = "test_airfresh_select"
    entity_id = await setup_component(hass, entity_name)

    select_entity = hass.states.get(entity_id + "_display_orientation")
    assert select_entity
    assert select_entity.state == "forward"
    assert select_entity.attributes.get(ATTR_OPTIONS) == ["forward", "left", "right"]


async def test_select_bad_attr(hass: HomeAssistant) -> None:
    """Test selecting a different option with invalid option value."""

    entity_name = "test_airfresh_select"
    entity_id = await setup_component(hass, entity_name)

    state = hass.states.get(entity_id + "_display_orientation")
    assert state
    assert state.state == "forward"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "up", ATTR_ENTITY_ID: entity_id + "_display_orientation"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id + "_display_orientation")
    assert state
    assert state.state == "forward"


async def test_select_option(hass: HomeAssistant) -> None:
    """Test selecting of a option."""

    entity_name = "test_airfresh_select"
    entity_id = await setup_component(hass, entity_name)

    state = hass.states.get(entity_id + "_display_orientation")
    assert state
    assert state.state == "forward"

    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "left", ATTR_ENTITY_ID: entity_id + "_display_orientation"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id + "_display_orientation")
    assert state
    assert state.state == "left"


async def test_select_coordinator_update(hass: HomeAssistant, setup_test) -> None:
    """Test coordinator update of a option."""

    entity_name = "test_airfresh_select"
    entity_id = await setup_component(hass, entity_name)

    state = hass.states.get(entity_id + "_display_orientation")
    assert state
    assert state.state == "forward"

    # emulate someone change state from device maybe used app
    setup_test.status().display_orientation = DisplayOrientation.LandscapeLeft

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id + "_display_orientation")
    assert state
    assert state.state == "left"


@pytest.mark.parametrize("model", [MODEL_AIRPURIFIER_4, MODEL_AIRPURIFIER_4_PRO])
async def test_select_led_brightness_reversed_models(
    hass: HomeAssistant, model: str
) -> None:
    """Test bright sends the reversed raw value on Air Purifier 4 models."""
    mock_airpurifier = MagicMock()
    mock_airpurifier.status().led_brightness = LedBrightness.Off

    with patch(
        "homeassistant.components.xiaomi_miio.AirPurifierMiot",
        return_value=mock_airpurifier,
    ):
        entity_id = await setup_component(hass, "test_airpurifier", model)
    entity_id += "_led_brightness"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "bright", ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_airpurifier.set_property.assert_called_once_with("led_brightness", 2)
    mock_airpurifier.set_led_brightness.assert_not_called()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "bright"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "dim", ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_airpurifier.set_led_brightness.assert_called_once_with(LedBrightness.Dim)
    mock_airpurifier.set_property.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "dim"


async def setup_component(
    hass: HomeAssistant, entity_name: str, model: str = MODEL_AIRFRESH_T2017
) -> str:
    """Set up component."""
    entity_id = f"{SELECT_DOMAIN}.{entity_name}"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        title=entity_name,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "0.0.0.0",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: model,
            CONF_MAC: TEST_MAC,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return entity_id
