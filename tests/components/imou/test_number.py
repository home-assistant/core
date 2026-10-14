"""Tests for Imou number platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import PARAM_REF, PARAM_STATE
from pyimouapi.exceptions import ImouException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imou.const import (
    OVERCHARGE_HIGH_REF,
    PARAM_COUNT_DOWN_SWITCH,
    PARAM_OVERCHARGE_SWITCH,
    PARAM_PLUG_SWITCH,
)
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_PLUG_TEXTS, create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

DEFAULT_PLUG_SWITCHES = {
    PARAM_PLUG_SWITCH: {PARAM_STATE: True},
}

PLUG_MOCK_DEVICES = [
    create_online_device(
        "plug1",
        "Smart plug",
        button_keys=(),
        switches=DEFAULT_PLUG_SWITCHES,
        texts=DEFAULT_PLUG_TEXTS,
    ),
]


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [PLUG_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_number_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot number entities created from the mock plug."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [PLUG_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_set_countdown_minutes(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Setting the countdown writes minutes and updates local state."""
    entity_id = "number.smart_plug_countdown_timer_min"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 15},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_imou_ha_device_manager.async_set_text_value.assert_called_once()
    assert hass.states.get(entity_id).state == "15.0"


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [PLUG_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_set_overcharge_watts(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Setting max power writes watts to the cloud API."""
    entity_id = "number.smart_plug_max_power_w"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 500},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_imou_ha_device_manager.async_set_text_value.assert_called_once_with(
        PLUG_MOCK_DEVICES[0],
        PARAM_OVERCHARGE_SWITCH,
        "500",
    )


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "plug2",
                "High plug",
                button_keys=(),
                switches={PARAM_PLUG_SWITCH: {PARAM_STATE: True}},
                texts={
                    PARAM_COUNT_DOWN_SWITCH: {PARAM_STATE: "0"},
                    PARAM_OVERCHARGE_SWITCH: {
                        PARAM_STATE: "2000",
                        PARAM_REF: OVERCHARGE_HIGH_REF,
                    },
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_overcharge_high_ref_allows_higher_max(hass: HomeAssistant) -> None:
    """Plugs with the high-power ref expose a larger watt ceiling."""
    entity_id = "number.high_plug_max_power_w"
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.attributes["max"]) == 3680.0


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [PLUG_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_set_countdown_imou_exception(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Cloud errors from set_text_value surface as translated failures."""
    mock_imou_ha_device_manager.async_set_text_value.side_effect = ImouException(
        "rejected"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.smart_plug_countdown_timer_min",
                ATTR_VALUE: 10,
            },
            blocking=True,
        )


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [PLUG_MOCK_DEVICES], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_countdown_expires_to_zero(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """The local clock drives the countdown down to zero without another poll."""
    entity_id = "number.smart_plug_countdown_timer_min"
    device = PLUG_MOCK_DEVICES[0]

    async def _set_countdown(dev, text_type, value):
        device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] = value

    mock_imou_ha_device_manager.async_set_text_value.side_effect = _set_countdown

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "0.0"
    assert device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] == "0"
