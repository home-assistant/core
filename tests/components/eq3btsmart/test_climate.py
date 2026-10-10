"""Test the eq3btsmart climate platform."""

from unittest.mock import MagicMock, patch

from eq3btsmart.const import Eq3Event
from eq3btsmart.exceptions import Eq3Exception
import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.eq3btsmart.const import (
    DOMAIN,
    SIGNAL_THERMOSTAT_CONNECTED,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import MAC

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device

ENTITY_ID = "climate.aa_bb_cc_dd_ee_ff"


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant, mock_thermostat: MagicMock) -> None:
    """Set up the integration with a connected thermostat."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: MAC},
        unique_id=format_mac(MAC),
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.eq3btsmart.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.eq3btsmart.bluetooth.async_ble_device_from_address",
            return_value=generate_ble_device(address=MAC, name="CC-RT-BLE"),
        ),
        patch("homeassistant.components.eq3btsmart._async_run_thermostat"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    async_dispatcher_send(hass, f"{SIGNAL_THERMOSTAT_CONNECTED}_{format_mac(MAC)}")
    status_callback = next(
        call.args[1]
        for call in mock_thermostat.register_callback.call_args_list
        if call.args[0] is Eq3Event.STATUS_RECEIVED
    )
    status_callback(None)
    await hass.async_block_till_done()


async def test_set_temperature_failed(
    hass: HomeAssistant, mock_thermostat: MagicMock
) -> None:
    """Test a failed temperature change raises and restores the target temperature."""
    mock_thermostat.async_set_temperature.side_effect = Eq3Exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )

    assert exc_info.value.translation_key == "set_temperature_failed"
    mock_thermostat.async_set_temperature.assert_awaited_once_with(22.0)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 20.0


async def test_set_hvac_mode_failed(
    hass: HomeAssistant, mock_thermostat: MagicMock
) -> None:
    """Test a failed HVAC mode change raises."""
    mock_thermostat.async_set_mode.side_effect = Eq3Exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.AUTO},
            blocking=True,
        )

    assert exc_info.value.translation_key == "set_hvac_mode_failed"
