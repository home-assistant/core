"""Tests for the diagnostics data provided by the VeSync integration."""

from types import SimpleNamespace

from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.vesync.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component


async def test_async_get_config_entry_diagnostics__no_devices(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    config: ConfigType,
    snapshot: SnapshotAssertion,
    manager,
) -> None:
    """Test diagnostics for config entry."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(diag, dict)
    assert diag == snapshot


async def test_async_get_config_entry_diagnostics__single_humidifier(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    config: ConfigType,
    snapshot: SnapshotAssertion,
    manager,
    humidifier,
) -> None:
    """Test diagnostics for config entry."""
    manager._dev_list["humidifiers"].append(humidifier)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(diag, dict)
    assert diag == snapshot


async def test_async_get_device_diagnostics__single_fan(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    config: ConfigType,
    snapshot: SnapshotAssertion,
    manager,
    fan,
) -> None:
    """Test diagnostics for config entry."""
    manager._dev_list["fans"].append(fan)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "fan"), config_entry.entry_id
    )
    assert device is not None

    diag = await get_diagnostics_for_device(hass, hass_client, config_entry, device)

    assert isinstance(diag, dict)
    diag["home_assistant"]["entities"] = sorted(
        diag["home_assistant"]["entities"], key=lambda ent: ent["entity_id"]
    )
    assert diag == snapshot(
        matcher=path_type(
            {
                r".*\.last_changed$": (str,),
                r".*\.last_updated$": (str,),
                r".*\.last_reported$": (str,),
            },
            regex=True,
        )
    )


async def test_async_get_device_diagnostics__subdevice_redacts_values(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    config: ConfigType,
    manager,
    fan,
) -> None:
    """Test sub-device matching and redaction in device diagnostics."""
    fan.sub_device_no = 7
    fan.manager = SimpleNamespace(secret="manager-secret")
    fan.uuid = "device-uuid"
    fan.mac_id = "device-mac"
    manager.devices.fans.append(fan)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "fan7"), config_entry.entry_id
    )
    assert device is not None

    manager.devices.outlets.append(SimpleNamespace(cid=None, sub_device_no=None))
    fan.state = SimpleNamespace(connection_status="online", mac_id="state-mac")

    diag = await get_diagnostics_for_device(hass, hass_client, config_entry, device)

    assert diag["manager"] == REDACTED
    assert diag["uuid"] == REDACTED
    assert diag["mac_id"] == REDACTED
    assert diag["state"]["mac_id"] == REDACTED
