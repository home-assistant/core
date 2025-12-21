"""The Goodwe inverter component."""

from goodwe import Inverter, InverterError, connect
from goodwe.const import GOODWE_UDP_PORT

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .config_flow import GoodweFlowHandler
from .const import CONF_MODEL_FAMILY, DOMAIN, PLATFORMS
from .coordinator import GoodweConfigEntry, GoodweRuntimeData, GoodweUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: GoodweConfigEntry) -> bool:
    """Set up the Goodwe components from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, GOODWE_UDP_PORT)
    model_family = entry.data[CONF_MODEL_FAMILY]

    # Connect to Goodwe inverter
    try:
        inverter = await connect(
            host=host,
            port=port,
            family=model_family,
            retries=10,
        )
    except InverterError as err:
        try:
            inverter = await async_check_port(hass, entry, host)
        except InverterError:
            raise ConfigEntryNotReady from err

    device_info = DeviceInfo(
        configuration_url="https://www.semsportal.com",
        identifiers={(DOMAIN, inverter.serial_number)},
        name=entry.title,
        manufacturer="GoodWe",
        model=inverter.model_name,
        sw_version=f"{inverter.firmware} / {inverter.arm_firmware}",
    )

    # Create update coordinator
    coordinator = GoodweUpdateCoordinator(hass, entry, inverter)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = GoodweRuntimeData(
        inverter=inverter,
        coordinator=coordinator,
        device_info=device_info,
    )

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_check_port(
    hass: HomeAssistant, entry: GoodweConfigEntry, host: str
) -> Inverter:
    """Check the communication port of the inverter, it may have changed after a firmware update."""
    inverter, port = await GoodweFlowHandler.async_detect_inverter_port(host=host)
    family = type(inverter).__name__
    hass.config_entries.async_update_entry(
        entry,
        data={
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_MODEL_FAMILY: family,
        },
    )
    return inverter


async def async_unload_entry(
    hass: HomeAssistant, config_entry: GoodweConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: GoodweConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: GoodweConfigEntry
) -> bool:
    """Migrate old config entries."""

    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        # Update from version 1 to version 2 adding the PROTOCOL to the config entry
        host = config_entry.data[CONF_HOST]
        try:
            inverter, port = await GoodweFlowHandler.async_detect_inverter_port(
                host=host
            )
        except InverterError as err:
            raise ConfigEntryNotReady from err
        new_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_MODEL_FAMILY: type(inverter).__name__,
        }
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)

    return True
