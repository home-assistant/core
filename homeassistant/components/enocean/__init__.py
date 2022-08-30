"""Support for EnOcean devices."""
from enocean.utils import combine_hex, to_hex_string
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .config_flow import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_NAME,
    CONF_ENOCEAN_DEVICES,
    CONF_ENOCEAN_EEP,
    CONF_ENOCEAN_MANUFACTURER,
    CONF_ENOCEAN_MODEL,
    CONF_ENOCEAN_SENDER_ID,
)
from .const import DATA_ENOCEAN, DOMAIN, ENOCEAN_DONGLE, LOGGER, PLATFORMS
from .dongle import EnOceanDongle
from .enocean_supported_device_type import EnOceanSupportedDeviceType

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)


# upcoming code is part of platform import to be deleted in a future version
class EnOceanPlatformConfig:
    """An EnOcean platform configuration entry."""

    platform: Platform
    config: ConfigType

    def __init__(self, platform: Platform, config: ConfigType) -> None:
        """Create a new EnOcean platform configuration entry."""
        self.platform = platform
        self.config = config


# upcoming code is part of platform import to be deleted in a future version
_enocean_platform_configs: list[EnOceanPlatformConfig] = []


# upcoming code is part of platform import to be deleted in a future version
def register_platform_config_for_migration_to_config_entry(
    platform_config: EnOceanPlatformConfig,
):
    """Register an EnOcean platform configuration for importing it to the config entry."""
    _enocean_platform_configs.append(platform_config)


# upcoming code is part of platform import to be deleted in a future version
def _get_entity_for_unique_id(ent_reg: entity_registry.EntityRegistry, unique_id):
    """Obtain an entity id even for those 'enocean' platform entities, which never had a device_class set.

    For some reason, this does not seem to be possible with the built-in async_get_entity_id(...) function.
    """
    for key in ent_reg.entities:
        ent = ent_reg.entities.get(key, None)
        if not ent:
            continue

        if ent.platform != "enocean":
            continue

        if ent.unique_id == unique_id:
            return ent

    return None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the EnOcean component."""
    # support for text-based configuration (legacy)
    if DOMAIN not in config:
        return True

    if hass.config_entries.async_entries(DOMAIN):
        # We can only have one dongle. If there is already one in the config,
        # there is no need to import the yaml based config.
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Set up an EnOcean dongle for the given entry."""
    enocean_data = hass.data.setdefault(DATA_ENOCEAN, {})
    usb_dongle = EnOceanDongle(hass, config_entry.data[CONF_DEVICE])
    await usb_dongle.async_setup()
    enocean_data[ENOCEAN_DONGLE] = usb_dongle

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    async_cleanup_device_registry(hass=hass, entry=config_entry)
    forward_entry_setup_to_platforms(hass=hass, entry=config_entry)

    enocean_devices_to_add = []

    # get the entity registry
    ent_reg = entity_registry.async_get(hass)

    # map from dev_id_string to list of (new) unique_ids
    new_unique_ids: dict[str, list[str]] = {}

    # map from dev_id_string to map from new unique_id to old unique_id
    old_unique_ids: dict[str, dict[str, str]] = {}

    # map from dev_id_string to map from (new) unique_id to old entity
    old_entities: dict[str, dict[str, entity_registry.RegistryEntry]] = {}

    # upcoming code is part of platform import to be deleted in a future version
    @callback
    def _schedule_yaml_import(_):
        """Schedule platform configuration import after HA is fully started."""
        if not _enocean_platform_configs or len(_enocean_platform_configs) < 1:
            return
        async_call_later(hass, 2, _import_yaml)

    # upcoming code is part of platform import to be deleted in a future version
    @callback
    def _import_yaml(_):
        """Import platform configuration to config entry."""
        LOGGER.warning(
            "EnOcean platform configurations were found in configuration.yaml. Configuring EnOcean via configuration.yaml is deprecated. Now starting automatic import to config entry... "
        )

        # get the unique config_entry and the devices configured in it
        conf_entries = hass.config_entries.async_entries("enocean")
        if not len(conf_entries) == 1:
            LOGGER.warning(
                "Cannot import platform configurations to config entry - no config entry found"
            )
            return
        config_entry = conf_entries[0]
        configured_enocean_devices = config_entry.options.get("devices", [])

        # process the platform configs
        for platform_config in _enocean_platform_configs:
            dev_id = platform_config.config.get("id", None)

            if not dev_id:
                LOGGER.warning(
                    "Skipping import of platform configuration with no EnOcean id"
                )
                continue

            dev_id_string = to_hex_string(dev_id)

            # check if device was already imported previously
            device_found = False
            for device in configured_enocean_devices:
                if device["id"] == to_hex_string(dev_id):
                    device_found = True
                    break

            if device_found:
                LOGGER.warning(
                    "Skipping import of EnOcean device %s because an EnOcean device with this EnOcean ID already exists in the config entry",
                    dev_id_string,
                )
                continue

            LOGGER.warning("To Import: %s", dev_id_string)

            new_unique_ids[dev_id_string] = []
            old_unique_ids[dev_id_string] = {}
            old_entities[dev_id_string] = {}

            if platform_config.platform == Platform.BINARY_SENSOR.value:
                new_unique_id = (
                    dev_id_string + "-" + Platform.BINARY_SENSOR.value + "-0"
                )
                new_unique_ids[dev_id_string].append(new_unique_id)

                device_class = platform_config.config.get("device_class", None)
                if device_class is None:
                    old_unique_ids[dev_id_string][new_unique_id] = (
                        str(combine_hex(dev_id)) + "-None"
                    )
                else:
                    old_unique_ids[dev_id_string][new_unique_id] = (
                        str(combine_hex(dev_id)) + "-" + device_class
                    )

            if platform_config.platform == Platform.BINARY_SENSOR.value:
                device_type = EnOceanSupportedDeviceType(
                    eep="F6-02-01",
                    manufacturer="Generic",
                    model="EEP F6-02-01 (Light and Blind Control - Application Style 2)",
                )

            if device_type is None:
                LOGGER.warning(
                    "Could not import EnOcean device %s: unknown device type",
                    dev_id_string,
                )

            # delete the old entities from entity registry
            for new_unique_id in new_unique_ids[dev_id_string]:
                old_entity = _get_entity_for_unique_id(
                    ent_reg, old_unique_ids[dev_id_string][new_unique_id]
                )

                if old_entity:
                    old_entities[dev_id_string][new_unique_id] = old_entity
                    ent_reg.async_remove(old_entity.entity_id)
                    LOGGER.warning(
                        "Removed entity '%s' from entity registry", old_entity.entity_id
                    )

            # append device
            enocean_devices_to_add.append(
                {
                    CONF_ENOCEAN_DEVICE_ID: dev_id_string,
                    CONF_ENOCEAN_EEP: device_type.eep,
                    CONF_ENOCEAN_MANUFACTURER: device_type.manufacturer,
                    CONF_ENOCEAN_MODEL: device_type.model,
                    CONF_ENOCEAN_DEVICE_NAME: platform_config.config.get(
                        "name", "Imported EnOcean device " + dev_id_string
                    ),
                    CONF_ENOCEAN_SENDER_ID: "",
                }
            )

        # append devices to config_entry and update
        for device in enocean_devices_to_add:
            configured_enocean_devices.append(device)

        hass.config_entries.async_update_entry(
            entry=config_entry,
            options={CONF_ENOCEAN_DEVICES: configured_enocean_devices},
        )

        async_call_later(hass, 10, _update_new_entities)

    async def _update_new_entities(self):
        # set values for the new entities:
        for device in enocean_devices_to_add:
            dev_id_string = device[CONF_ENOCEAN_DEVICE_ID]
            LOGGER.warning("Now processing new entities for device %s", dev_id_string)

            for new_unique_id in new_unique_ids[dev_id_string]:

                LOGGER.warning("Entity: %s", new_unique_id)

                new_entity = _get_entity_for_unique_id(ent_reg, new_unique_id)

                if new_entity is None:
                    LOGGER.warning("Entity not found")
                    continue

                old_entity = old_entities[dev_id_string].get(new_unique_id, None)

                if old_entity is None:
                    continue

                new_name = None
                if new_entity.name is not None:
                    new_name = old_entity.name

                ent_reg.async_update_entity(
                    entity_id=new_entity.entity_id,
                    new_entity_id=old_entity.entity_id,
                    area_id=old_entity.area_id,
                    device_class=old_entity.device_class,
                    icon=old_entity.icon,
                    name=new_name,
                )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _schedule_yaml_import)

    return True


@callback
def async_cleanup_device_registry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove entries from device registry if device is removed."""

    device_registry = dr.async_get(hass)
    hass_devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=entry.entry_id,
    )

    device_ids = [dev["id"].upper() for dev in entry.options.get("devices", [])]

    for hass_device in hass_devices:
        for item in hass_device.identifiers:
            domain = item[0]
            device_id = (str(item[1]).split("-", maxsplit=1)[0]).upper()
            if DOMAIN == domain and device_id not in device_ids:
                LOGGER.debug(
                    "Removing Home Assistant device %s and associated entities for EnOcean device %s",
                    hass_device.id,
                    device_id,
                )
                device_registry.async_update_device(
                    hass_device.id, remove_config_entry_id=entry.entry_id
                )
                break


def forward_entry_setup_to_platforms(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Forward entry setup to all implemented platforms."""
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry=entry, domain=platform)
        )


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EnOcean config entry."""
    enocean_dongle = hass.data[DATA_ENOCEAN][ENOCEAN_DONGLE]
    enocean_dongle.unload()

    if unload_platforms := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        hass.data.pop(DATA_ENOCEAN)

    return unload_platforms
