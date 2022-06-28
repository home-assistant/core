"""Tests for Broadlink remotes."""
from __future__ import annotations

from base64 import b64decode
from unittest.mock import call

import pytest

from homeassistant.components.broadlink import BroadlinkData
from homeassistant.components.broadlink.device import BroadlinkStores
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device


def _get_states(
    hass: HomeAssistant, device_id: str, subdevice: str, attributes: set[str]
):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device_entry = device_registry.async_get_device(
        {("broadlink", f"{device_id}-codes-{subdevice}")}
    )
    assert device_entry

    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    return {
        state.entity_id: {
            attribute_name: attribute
            for attribute_name in attributes
            if (attribute := state.attributes.get(attribute_name)) is not None
        }
        for entry in entries
        if entry.domain == Platform.BUTTON
        and (state := hass.states.get(entry.entity_id))
    }


@pytest.mark.parametrize(
    ("subdevice, result"),
    [
        (
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
    subdevice: str,
    result: dict,
):
    """Test a successful setup with all remotes."""
    device = get_device("Entrance")
    setup = await device.setup_entry(hass)
    device_id = setup.entry.unique_id

    states = _get_states(hass, device_id, subdevice, {"friendly_name"})

    assert states == result


@pytest.mark.parametrize(
    ("subdevice, result, commands"),
    [
        (
            "smsl",
            {
                "button.smsl_toggled": {"friendly_name": "smsl toggled"},
                "button.smsl_standby": {
                    "friendly_name": "smsl standby",
                },
                "button.smsl_dummy": {"friendly_name": "smsl dummy"},
            },
            {"dummy": "1234"},
        ),
        (
            "added_device",
            {
                "button.added_device_dummy": {"friendly_name": "added_device dummy"},
            },
            {"dummy": "1234"},
        ),
    ],
)
async def test_button_adding(
    hass: HomeAssistant,
    subdevice: str,
    commands: dict[str, str | list[str]],
    result: dict,
):
    """Test a successful setup with all remotes."""

    device = get_device("Entrance")
    setup = await device.setup_entry(hass)
    device_id = setup.entry.unique_id

    data: BroadlinkData = hass.data["broadlink"]
    stores: BroadlinkStores = data.devices[setup.entry.entry_id].store
    stores.add_commands(commands, subdevice)
    await hass.async_block_till_done()

    states = _get_states(hass, device_id, subdevice, {"friendly_name"})

    assert states == result


@pytest.mark.parametrize(
    ("subdevice, result, commands"),
    [
        (
            "smsl",
            {
                "button.smsl_toggled": {"friendly_name": "smsl toggled"},
            },
            ["standby"],
        ),
    ],
)
async def test_button_deleting(
    hass: HomeAssistant,
    subdevice: str,
    commands: list[str],
    result: dict,
):
    """Test a successful setup with all remotes."""

    device = get_device("Entrance")
    setup = await device.setup_entry(hass)
    device_id = setup.entry.unique_id

    data: BroadlinkData = hass.data["broadlink"]
    stores: BroadlinkStores = data.devices[setup.entry.entry_id].store
    stores.delete_commands(commands, subdevice)
    await hass.async_block_till_done()

    states = _get_states(hass, device_id, subdevice, {"friendly_name"})

    assert states == result


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
