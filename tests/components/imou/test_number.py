"""Tests for Imou number platform."""

from unittest.mock import MagicMock

from pyimouapi.const import PARAM_REF, PARAM_STATE
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
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

DEFAULT_PLUG_SWITCHES = {
    PARAM_PLUG_SWITCH: {PARAM_STATE: True},
}


def plug_mock_devices() -> list[ImouHaDevice]:
    """Return a fresh smart-plug device list for each test."""
    return [
        create_online_device(
            "plug1",
            "Smart plug",
            button_keys=(),
            switches=DEFAULT_PLUG_SWITCHES,
            texts=DEFAULT_PLUG_TEXTS,
        )
    ]


def high_plug_mock_devices() -> list[ImouHaDevice]:
    """Return a fresh high-power plug for each test."""
    return [
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


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
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
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_set_overcharge_watts(
    hass: HomeAssistant,
    mock_imou_ha_device_manager: MagicMock,
    imou_mock_devices: list[ImouHaDevice],
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
        imou_mock_devices[0],
        PARAM_OVERCHARGE_SWITCH,
        "500",
    )


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [high_plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_overcharge_high_ref_allows_higher_max(hass: HomeAssistant) -> None:
    """Plugs with the high-power ref expose a larger watt ceiling."""
    entity_id = "number.high_plug_max_power_w"
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.attributes["max"]) == 3680.0


@pytest.mark.parametrize("platforms", [[Platform.NUMBER]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_set_overcharge_imou_exception(
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
                ATTR_ENTITY_ID: "number.smart_plug_max_power_w",
                ATTR_VALUE: 500,
            },
            blocking=True,
        )
