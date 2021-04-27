"""Tests for 1-Wire integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pyownet.protocol import ProtocolError

from homeassistant.components.onewire.const import (
    CONF_MOUNT_DIR,
    CONF_NAMES,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE

from .const import MOCK_OWPROXY_DEVICES, MOCK_SYSBUS_DEVICES

from tests.common import MockConfigEntry


async def setup_onewire_sysbus_integration(hass):
    """Create the 1-Wire integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_TYPE: CONF_TYPE_SYSBUS,
            CONF_MOUNT_DIR: DEFAULT_SYSBUS_MOUNT_DIR,
        },
        unique_id=f"{CONF_TYPE_SYSBUS}:{DEFAULT_SYSBUS_MOUNT_DIR}",
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="1",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def setup_onewire_owserver_integration(hass):
    """Create the 1-Wire integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
        },
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="2",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        return config_entry


async def setup_onewire_patched_owserver_integration(hass):
    """Create the 1-Wire integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
            CONF_NAMES: {
                "10.111111111111": "My DS18B20",
            },
        },
        connection_class=CONN_CLASS_LOCAL_POLL,
        options={},
        entry_id="2",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


def setup_owproxy_mock_devices(owproxy, domain, device_ids) -> None:
    """Set up mock for owproxy."""
    dir_return_value = []
    main_read_side_effect = []
    sub_read_side_effect = []

    for device_id in device_ids:
        mock_device = MOCK_OWPROXY_DEVICES[device_id]

        # Setup directory listing
        dir_return_value += [f"/{device_id}/"]

        # Setup device reads
        main_read_side_effect += [device_id[0:2].encode()]
        if "inject_reads" in mock_device:
            main_read_side_effect += mock_device["inject_reads"]

        # Setup sub-device reads
        device_sensors = mock_device.get(domain, [])
        for expected_sensor in device_sensors:
            sub_read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect = (
        main_read_side_effect
        + sub_read_side_effect
        + [ProtocolError("Missing injected value")] * 20
    )
    owproxy.return_value.dir.return_value = dir_return_value
    owproxy.return_value.read.side_effect = read_side_effect


def setup_sysbus_mock_devices(
    domain: str, device_ids: list[str]
) -> tuple[list[str], list[Any]]:
    """Set up mock for sysbus."""
    glob_result = []
    read_side_effect = []

    for device_id in device_ids:
        mock_device = MOCK_SYSBUS_DEVICES[device_id]

        # Setup directory listing
        glob_result += [f"/{DEFAULT_SYSBUS_MOUNT_DIR}/{device_id}"]

        # Setup sub-device reads
        device_sensors = mock_device.get(domain, [])
        for expected_sensor in device_sensors:
            if isinstance(expected_sensor["injected_value"], list):
                read_side_effect += expected_sensor["injected_value"]
            else:
                read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect.extend([FileNotFoundError("Missing injected value")] * 20)

    return (glob_result, read_side_effect)
