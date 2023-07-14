"""API for Zigbee Home Automation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from zigpy.backups import NetworkBackup
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.types import Channels
from zigpy.util import pick_optimal_channel

from .core.const import (
    CONF_RADIO_TYPE,
    DATA_ZHA,
    DATA_ZHA_CONFIG,
    DATA_ZHA_GATEWAY,
    DOMAIN,
    RadioType,
)
from .core.gateway import ZHAGateway

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _get_gateway(hass: HomeAssistant) -> ZHAGateway:
    """Get a reference to the ZHA gateway device."""
    return hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]


def _get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Find the singleton ZHA config entry, if one exists."""

    # If ZHA is already running, use its config entry
    try:
        zha_gateway = _get_gateway(hass)
    except KeyError:
        pass
    else:
        return zha_gateway.config_entry

    # Otherwise, find one
    entries = hass.config_entries.async_entries(DOMAIN)

    if len(entries) != 1:
        raise ValueError(f"Invalid number of ZHA config entries: {entries!r}")

    return entries[0]


def async_get_active_network_settings(hass: HomeAssistant) -> NetworkBackup:
    """Get the network settings for the currently active ZHA network."""
    zha_gateway: ZHAGateway = _get_gateway(hass)
    app = zha_gateway.application_controller

    return NetworkBackup(
        node_info=app.state.node_info,
        network_info=app.state.network_info,
    )


async def async_get_last_network_settings(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> NetworkBackup | None:
    """Get the network settings for the last-active ZHA network."""
    if config_entry is None:
        config_entry = _get_config_entry(hass)

    config = hass.data.get(DATA_ZHA, {}).get(DATA_ZHA_CONFIG, {})
    zha_gateway = ZHAGateway(hass, config, config_entry)

    app_controller_cls, app_config = zha_gateway.get_application_controller_data()
    app = app_controller_cls(app_config)

    try:
        await app._load_db()  # pylint: disable=protected-access
        settings = max(app.backups, key=lambda b: b.backup_time)
    except ValueError:
        settings = None
    finally:
        await app.shutdown()

    return settings


async def async_get_network_settings(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> NetworkBackup | None:
    """Get ZHA network settings, preferring the active settings if ZHA is running."""

    try:
        return async_get_active_network_settings(hass)
    except KeyError:
        return await async_get_last_network_settings(hass, config_entry)


def async_get_radio_type(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> RadioType:
    """Get ZHA radio type."""
    if config_entry is None:
        config_entry = _get_config_entry(hass)

    return RadioType[config_entry.data[CONF_RADIO_TYPE]]


def async_get_radio_path(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> str:
    """Get ZHA radio path."""
    if config_entry is None:
        config_entry = _get_config_entry(hass)

    return config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH]


async def async_change_channel(
    hass: HomeAssistant, new_channel: int | Literal["auto"]
) -> None:
    """Migrate the ZHA network to a new channel."""

    zha_gateway: ZHAGateway = _get_gateway(hass)
    app = zha_gateway.application_controller

    if new_channel == "auto":
        channel_energy = await app.energy_scan(
            channels=Channels.ALL_CHANNELS,
            duration_exp=4,
            count=1,
        )
        new_channel = pick_optimal_channel(channel_energy)

    await app.move_network_to_channel(new_channel)
