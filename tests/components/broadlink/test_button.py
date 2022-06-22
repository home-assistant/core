"""Tests for Broadlink remotes."""

from base64 import b64decode
from unittest.mock import call

import pytest

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_entries_for_device

from . import get_device

from tests.common import mock_device_registry, mock_registry


@pytest.mark.parametrize(
    ("device_name, device_id, subdevice, result_entries"),
    [
        (
            "Entrance",
            "34ea34befc25",
            "smsl",
            {
                "button.smsl_toggled": {"friendly_name": "smsl toggled"},
                "button.smsl_standby": {
                    "friendly_name": "smsl standby",
                },
            },
        )
    ],
)
async def test_button_setup_works(
    hass: HomeAssistant,
    device_name: str,
    device_id: str,
    subdevice: str,
    result_entries: dict,
):
    """Test a successful setup with all remotes."""
    device = get_device(device_name)
    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)
    await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        {("broadlink", f"{device_id}-codes-{subdevice}")}
    )
    assert device_entry

    entries = async_entries_for_device(entity_registry, device_entry.id)
    states = {
        state.entity_id: {
            attribute_name: attribute
            for attribute_name in ["friendly_name"]
            if (attribute := state.attributes.get(attribute_name)) is not None
        }
        for entry in entries
        if entry.domain == Platform.BUTTON
        and (state := hass.states.get(entry.entity_id))
    }

    assert states == result_entries


@pytest.mark.parametrize(
    ("device_name, entity_ids, result_calls"),
    [
        (
            "Entrance",
            ["button.smsl_standby"],
            [
                "JgBYAAABJpcTEhM4ERMSExE5EhMSFBAVExIQFRA6ExIROhA6EBUQFRE6ExIRFBAVEBURFBEUERQTEhE5EToTOBA5EzkQORE6EwAFkAABKUoTAAxiAAEoSxEADQU="
            ],
        ),
        (
            "Entrance",
            [
                "button.smsl_toggled",
                "button.smsl_toggled",
                "button.smsl_toggled",
            ],
            [
                "JgBYAAABJpcQFRA6ERQTEhE5ExIRFBIUERQQFRE5FBEROhA6EhMSExE6ExIRFBAVEBUQFREUEBUTEhE5EToRORI4EToRORM4EgAFkQABJ0sRAAxlAAEmTBIADQU=",
                "JgBYAAABJ5YRFBE6EhMQFRA6EhMSExEVEjgSExE5ExITOBE5ERQTExE5ExIRFBITERQRFBEUERUQFRA6EToSOBI5EjgRORI5EwAFawABJk0QAAxlAAEoSxIADQU=",
                "JgBYAAABJpcQFRA6ERQTEhE5ExIRFBIUERQQFRE5FBEROhA6EhMSExE6ExIRFBAVEBUQFREUEBUTEhE5EToRORI4EToRORM4EgAFkQABJ0sRAAxlAAEmTBIADQU=",
            ],
        ),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    device_name: str,
    entity_ids: str,
    result_calls: list,
):
    """Test a successful setup with all remotes."""
    device = get_device(device_name)
    mock_setup = await device.setup_entry(hass)

    for entity_id in entity_ids:
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {"entity_id": entity_id},
            blocking=True,
        )

    assert mock_setup.api.send_data.call_count == len(result_calls)
    assert mock_setup.api.send_data.call_args_list == [
        call(b64decode(result_call)) for result_call in result_calls
    ]
    assert mock_setup.api.auth.call_count == 1
