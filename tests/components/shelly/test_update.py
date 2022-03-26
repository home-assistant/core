"""Tests for Shelly button platform."""
import pytest

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update.const import SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "status,result_state",
    [
        ({"update": None}, STATE_UNKNOWN),
        (
            {
                "update": {
                    "has_update": False,
                    "old_version": "latest_greatest",
                    "new_version": "latest_greatest",
                },
            },
            STATE_OFF,
        ),
        (
            {
                "update": {
                    "has_update": False,
                    "old_version": "latest_greatest",
                    "new_version": None,
                },
            },
            STATE_OFF,
        ),
        (
            {},
            STATE_ON,
        ),
    ],
)
async def test_coap_update_entity(
    hass: HomeAssistant, coap_wrapper, status: dict, result_state
):
    """Test coap update entities."""
    assert coap_wrapper
    coap_wrapper.device.status = {**coap_wrapper.device.status, **status}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, UPDATE_DOMAIN)
    )
    await hass.async_block_till_done()

    # stable channel update entity
    state = hass.states.get("update.test_name_firmware_update")
    assert state
    assert state.state == result_state

    if result_state == STATE_ON:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert coap_wrapper.device.trigger_ota_update.call_count == 1
        coap_wrapper.device.trigger_ota_update.assert_called_with(beta=False)


@pytest.mark.parametrize(
    "status,shelly,result_state",
    [
        (
            {"sys": {"available_updates": {"stable": {"version": "lates_greatest"}}}},
            {},
            STATE_OFF,
        ),
        (
            {},
            None,
            STATE_UNKNOWN,
        ),
        (
            {"sys": {"available_updates": None}},
            {},
            STATE_UNKNOWN,
        ),
        (
            {},
            {},
            STATE_ON,
        ),
    ],
)
async def test_rpc_update_entity(
    hass: HomeAssistant, rpc_wrapper, status, shelly, result_state
):
    """Test rpc update entities."""
    assert rpc_wrapper
    rpc_wrapper.device.status = {**rpc_wrapper.device.status, **status}

    if shelly is not None:
        rpc_wrapper.device.shelly = {**rpc_wrapper.device.shelly, **shelly}
    else:
        rpc_wrapper.device.shelly = None

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, UPDATE_DOMAIN)
    )
    await hass.async_block_till_done()

    # stable channel update entity
    state = hass.states.get("update.test_name_firmware_update")
    assert state
    assert state.state == result_state

    if result_state == STATE_ON:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert rpc_wrapper.device.trigger_ota_update.call_count == 1
        rpc_wrapper.device.trigger_ota_update.assert_called_with(beta=False)
