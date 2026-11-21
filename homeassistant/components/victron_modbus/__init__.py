"""The Victron Modbus integration.

Every supported device is a Modbus/UDP device. This integration does not own
its connection: it borrows a ``ModbusUnit`` from the shared ``modbus``
integration, keyed on this entry's host, and hands it to the matching device
class from the ``victron_modbus`` library (see ``models.py``). ``modbus`` owns
the connection lifecycle, transparently shares it with any other integration
pointed at the same host, and closes it once the last entry holding a unit on
it unloads.
"""

from modbus_connection import ModbusError, ModbusUdpParams
from victron_modbus import UnsupportedDeviceError, async_identify

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN, PORT, UNIT_ID
from .coordinator import VictronModbusConfigEntry, VictronModbusData
from .models import MODELS

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: VictronModbusConfigEntry
) -> None:
    """Set up a Victron Modbus device from a config entry."""
    unit = async_get_unit(
        hass, entry, ModbusUdpParams(host=entry.data[CONF_HOST], port=PORT), UNIT_ID
    )
    # Identify the device before reading anything model-specific, so another
    # device at this address is refused even when it rejects those reads.
    try:
        device = await async_identify(unit)
    except UnsupportedDeviceError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="device_mismatch"
        ) from err
    except ModbusError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    if (
        device.info.serial_number != entry.unique_id
        or type(device) is not MODELS[entry.data[CONF_MODEL]].device_class
    ):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="device_mismatch"
        )

    data = VictronModbusData.create(hass, entry, device)
    await data.power.async_config_entry_first_refresh()
    await data.readings.async_config_entry_first_refresh()

    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: VictronModbusConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
