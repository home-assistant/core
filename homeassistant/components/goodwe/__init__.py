"""The Goodwe inverter component."""

from goodwe import Inverter, InverterError, connect
from goodwe.const import GOODWE_TCP_PORT, GOODWE_UDP_PORT

from homeassistant.const import CONF_HOST, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .config_flow import GoodweFlowHandler
from .const import CONF_MODEL_FAMILY, DOMAIN, PLATFORMS, PROTOCOL_TCP, PROTOCOL_UDP
from .coordinator import GoodweConfigEntry, GoodweRuntimeData, GoodweUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: GoodweConfigEntry) -> bool:
    """Set up the Goodwe components from a config entry or updates an old config entry before setting up."""
    host = entry.data[CONF_HOST]
    protocol = entry.data[CONF_PROTOCOL]
    model_family = entry.data[CONF_MODEL_FAMILY]
    port = _get_port(protocol)
    # Connect to Goodwe inverter
    try:
        inverter = await connect(
            host=host,
            port=port,
            family=model_family,
            retries=10,
        )
    except InverterError as err:
        # Try to reconfigure the Inverter
        try:
            inverter = await async_reconfigure_entry(hass, entry, host)
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


def _get_port(protocol):
    if protocol == PROTOCOL_UDP:
        port = GOODWE_UDP_PORT
    elif protocol == PROTOCOL_TCP:
        port = GOODWE_TCP_PORT
    return port


async def async_reconfigure_entry(
    hass: HomeAssistant, entry: GoodweConfigEntry, host: str
) -> Inverter:
    """Try to reconfigure an Inverter that is not able to be connected with actual config. Actual host could be reused by a new Inverter with a different protocol."""
    inverter, protocol = await GoodweFlowHandler.async_detect_inverter_port(host=host)
    family = (type(inverter).__name__,)
    hass.config_entries.async_update_entry(
        entry,
        data={
            CONF_HOST: host,
            CONF_PROTOCOL: protocol,
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
            inverter, protocol = await GoodweFlowHandler.async_detect_inverter_port(
                host=host
            )
        except InverterError as err:
            raise ConfigEntryNotReady from err
        new_data = {
            CONF_HOST: host,
            CONF_PROTOCOL: protocol,
            CONF_MODEL_FAMILY: type(inverter).__name__,
        }
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)

    return True
