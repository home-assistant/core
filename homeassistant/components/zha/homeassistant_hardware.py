"""Home Assistant Hardware firmware utilities."""

import logging

from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningIntegration,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .helpers import get_zha_gateway

_LOGGER = logging.getLogger(__name__)


@callback
def get_firmware_info(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> FirmwareInfo | None:
    """Return firmware information for the ZHA instance, synchronously."""

    # We only support EZSP firmware for now
    if config_entry.data.get("radio_type", None) != "ezsp":
        return None

    if (device := config_entry.data.get("device", {}).get("path")) is None:
        return None

    try:
        gateway = get_zha_gateway(hass)
    except ValueError:
        firmware_version = None
    else:
        firmware_version = gateway.state.node_info.version

    return FirmwareInfo(
        device=device,
        firmware_type=ApplicationType.EZSP,
        firmware_version=firmware_version,
        source=DOMAIN,
        owners=[OwningIntegration(config_entry_id=config_entry.entry_id)],
    )


async def async_update_device_path(
    hass: HomeAssistant, config_entry: ConfigEntry, new_path: str
) -> None:
    """Follow the radio to a new serial port path."""

    # Only the path changes: a wrong radio is still caught when setup compares its
    # network against the backup
    device = config_entry.data[CONF_DEVICE]
    if device[CONF_DEVICE_PATH] == new_path:
        return

    _LOGGER.debug(
        "Following the radio from %s to %s", device[CONF_DEVICE_PATH], new_path
    )
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_DEVICE: {**device, CONF_DEVICE_PATH: new_path},
        },
    )

    # A retrying entry is waiting on exactly this; a loaded one is talking to a port
    # that no longer has the radio behind it
    if config_entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
        hass.config_entries.async_schedule_reload(config_entry.entry_id)
