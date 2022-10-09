"""Support for EnOcean devices."""
from __future__ import annotations

from copy import deepcopy

from enocean.utils import combine_hex, from_hex_string, to_hex_string
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
from .enocean_supported_device_type import (
    EEP_D2_01_07,
    EEP_D2_01_11,
    EEP_D2_01_13,
    EEP_D2_01_14,
    EEP_F6_02_01,
    EnOceanSupportedDeviceType,
)

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


class EnOceanImportConfig:
    """An EnOcean import configuration."""

    new_unique_id: str
    old_unique_id: str
    device_type: EnOceanSupportedDeviceType | None

    def __init__(
        self,
        new_unique_id: str,
        old_unique_id: str,
        device_type: EnOceanSupportedDeviceType | None,
    ) -> None:
        """Create a new EnOcean import configuration."""
        self.new_unique_id = new_unique_id
        self.old_unique_id = old_unique_id
        self.device_type = device_type


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

    return _setup_yaml_import(hass, _enocean_platform_configs)


# upcoming code is part of platform import to be deleted in a future version
def _setup_yaml_import(
    hass: HomeAssistant,
    enocean_platform_configs: list[EnOceanPlatformConfig],
) -> bool:
    enocean_devices_to_add: list[dict[str, str]] = []
    ent_reg = entity_registry.async_get(hass)

    # map from dev_id_string to list of (new) unique_ids
    new_unique_ids: dict[str, list[str]] = {}

    # map from dev_id_string to map from new unique_id to old unique_id
    old_unique_ids: dict[str, dict[str, str]] = {}

    # map from dev_id_string to map from (new) unique_id to old entity
    old_entities: dict[str, dict[str, entity_registry.RegistryEntry]] = {}

    @callback
    def _schedule_yaml_import(_):
        """Schedule platform configuration import 2s after HA is fully started."""
        if not _enocean_platform_configs or len(_enocean_platform_configs) < 1:
            return
        async_call_later(hass, 2, _import_yaml)

    @callback
    def _import_yaml(_):
        """Import platform configuration to config entry."""
        LOGGER.warning(
            "EnOcean platform configurations were found in configuration.yaml. Configuring EnOcean via configuration.yaml is deprecated and will be removed in a future release. Now starting automatic import to config entry... "
        )

        # get the unique config_entry and the devices configured in it
        conf_entries = hass.config_entries.async_entries("enocean")
        if not len(conf_entries) == 1:
            LOGGER.warning(
                "Cannot import platform configurations to config entry - no config entry found"
            )
            return
        config_entry = conf_entries[0]

        configured_enocean_devices = deepcopy(
            config_entry.options.get(CONF_ENOCEAN_DEVICES, [])
        )

        # group platform configs by id
        enocean_platform_configs_by_id: dict[str, list[EnOceanPlatformConfig]] = {}
        for platform_config in enocean_platform_configs:
            dev_id = platform_config.config.get(CONF_ENOCEAN_DEVICE_ID, None)

            if not dev_id:
                LOGGER.warning(
                    "Skipping import of platform configuration with no EnOcean id"
                )
                continue

            dev_id_string = to_hex_string(dev_id)

            if dev_id_string not in enocean_platform_configs_by_id:
                enocean_platform_configs_by_id[dev_id_string] = [platform_config]
            else:
                enocean_platform_configs_by_id[dev_id_string].append(platform_config)

        # process the enocean platform configs by id
        for dev_id_string, platform_configs in enocean_platform_configs_by_id.items():
            LOGGER.debug(
                "Device '%s' has '%i' platform configs",
                dev_id_string,
                len(enocean_platform_configs_by_id[dev_id_string]),
            )

            dev_id = from_hex_string(dev_id_string)

            if _is_configured(
                dev_id=dev_id, configured_enocean_devices=configured_enocean_devices
            ):
                LOGGER.warning(
                    "Skipping import of already imported EnOcean device %s",
                    dev_id_string,
                )
                continue

            new_unique_ids[dev_id_string] = []
            old_unique_ids[dev_id_string] = {}
            old_entities[dev_id_string] = {}

            for platform_config in platform_configs:
                import_config: EnOceanImportConfig = _get_import_config(
                    dev_id_string=dev_id_string,
                    dev_id=dev_id,
                    platform_config=platform_config,
                    enocean_devices_to_add=enocean_devices_to_add,
                )

                new_unique_ids[dev_id_string].append(import_config.new_unique_id)
                old_unique_ids[dev_id_string][
                    import_config.new_unique_id
                ] = import_config.old_unique_id

                if import_config.device_type is not None:
                    enocean_devices_to_add.append(
                        {
                            CONF_ENOCEAN_DEVICE_ID: dev_id_string,
                            CONF_ENOCEAN_EEP: import_config.device_type.eep,
                            CONF_ENOCEAN_MANUFACTURER: import_config.device_type.manufacturer,
                            CONF_ENOCEAN_MODEL: import_config.device_type.model,
                            CONF_ENOCEAN_DEVICE_NAME: platform_config.config.get(
                                "name", "Imported EnOcean device " + dev_id_string
                            ),
                            CONF_ENOCEAN_SENDER_ID: "",
                        }
                    )

                    LOGGER.warning(
                        "Scheduling EnOcean device %s for import as '%s %s' [EEP %s]",
                        dev_id_string,
                        import_config.device_type.manufacturer,
                        import_config.device_type.model,
                        import_config.device_type.eep,
                    )

        if len(enocean_devices_to_add) < 1:
            LOGGER.warning(
                "Import of EnOcean platform configurations completed (no new devices)"
            )
            return

        # append devices to config_entry and update
        for device in enocean_devices_to_add:
            configured_enocean_devices.append(device)

        hass.config_entries.async_update_entry(
            entry=config_entry,
            options={CONF_ENOCEAN_DEVICES: configured_enocean_devices},
        )

        async_call_later(hass, 5, _remove_new_entities_and_update_old_entities)

    async def _remove_new_entities_and_update_old_entities(self):
        # set values for the old entities:
        for device in enocean_devices_to_add:
            dev_id_string = device[CONF_ENOCEAN_DEVICE_ID]
            LOGGER.debug(
                "Updating entities for imported EnOcean device %s", dev_id_string
            )

            for new_unique_id in new_unique_ids[dev_id_string]:
                old_unique_id = old_unique_ids[dev_id_string][new_unique_id]

                # get both the new and the old entity
                new_entity = _get_entity_for_unique_id(ent_reg, new_unique_id)
                old_entity = _get_entity_for_unique_id(ent_reg, old_unique_id)

                # if no new entity was found, nothing can be done (this should never happen)
                if new_entity is None:
                    LOGGER.warning(
                        "No new entity with unique id '%s' found", new_unique_id
                    )
                    continue

                # if there was no old entity, there is nothing to be done (this should never happen)
                if old_entity is None:
                    LOGGER.warning(
                        "No old entity with unique id '%s' found", old_unique_id
                    )
                    continue

                # remove the new entity
                ent_reg.async_remove(new_entity.entity_id)
                LOGGER.debug(
                    "Removed new entity '%s' with unique_id '%s' from entity registry",
                    new_entity.entity_id,
                    new_unique_id,
                )

                ent_reg.async_update_entity(
                    entity_id=old_entity.entity_id,
                    new_unique_id=new_unique_id,
                    device_id=new_entity.device_id,
                )

                LOGGER.debug(
                    "Updated old entity '%s' in entity registry: Its new unique_id is '%s' (previously '%s') and its device_id is '%s' (previously NULL). You need to restart Home Assistant for this entity to show up in the UI",
                    old_entity.entity_id,
                    new_unique_id,
                    old_unique_id,
                    new_entity.device_id,
                )

        LOGGER.warning(
            "Import of EnOcean platform configurations completed. Please delete these entries from your configuration.yaml and restart Home Assistant"
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _schedule_yaml_import)

    return True


def _is_configured(dev_id, configured_enocean_devices):
    """Check if an EnOcean device with the given id was already configured."""
    for device in configured_enocean_devices:
        if device[CONF_ENOCEAN_DEVICE_ID] == to_hex_string(dev_id):
            return True

    return False


def _get_import_config(
    dev_id_string: str,
    platform_config: EnOceanPlatformConfig,
    dev_id,
    enocean_devices_to_add,
):
    """Return an import configuration for the supplied platform configuration."""
    if platform_config.platform == Platform.BINARY_SENSOR.value:
        return _get_binary_sensor_import_config(
            dev_id_string=dev_id_string,
            platform_config=platform_config,
            dev_id=dev_id,
        )

    if platform_config.platform == Platform.LIGHT.value:
        return _get_light_import_config(dev_id_string=dev_id_string, dev_id=dev_id)

    if platform_config.platform == Platform.SWITCH.value:
        return _get_switch_import_config(
            dev_id_string=dev_id_string,
            platform_config=platform_config,
            dev_id=dev_id,
            enocean_devices_to_add=enocean_devices_to_add,
        )


def _get_binary_sensor_import_config(
    dev_id_string: str, platform_config: EnOceanPlatformConfig, dev_id
) -> EnOceanImportConfig:
    """Return an import config for a binary sensor."""
    new_unique_id = dev_id_string + "-" + Platform.BINARY_SENSOR.value + "-0"

    device_class = platform_config.config.get("device_class", None)
    if device_class is None:
        old_unique_id = str(combine_hex(dev_id)) + "-None"
    else:
        old_unique_id = str(combine_hex(dev_id)) + "-" + device_class

    return EnOceanImportConfig(
        new_unique_id=new_unique_id,
        old_unique_id=old_unique_id,
        device_type=EEP_F6_02_01,
    )


def _get_light_import_config(dev_id_string: str, dev_id) -> EnOceanImportConfig:
    """Return an import config for a light."""
    new_unique_id = dev_id_string + "-" + Platform.LIGHT.value + "-0"
    old_unique_id = str(combine_hex(dev_id))

    device_type = EnOceanSupportedDeviceType(
        eep="A5-38-08_EltakoFUD61", manufacturer="Eltako", model="FUD61NPN"
    )

    return EnOceanImportConfig(
        new_unique_id=new_unique_id,
        old_unique_id=old_unique_id,
        device_type=device_type,
    )


def _get_switch_import_config(
    dev_id_string: str,
    platform_config: EnOceanPlatformConfig,
    dev_id,
    enocean_devices_to_add,
) -> EnOceanImportConfig:
    """Return an import config for a switch."""
    required_channels = 1
    channel = platform_config.config.get("channel", 0)

    device_type = None
    required_channels, device_type = _switch_get_required_channels_and_eep(channel)

    new_unique_id = dev_id_string + "-" + Platform.SWITCH.value + "-" + str(channel)

    old_unique_id = str(combine_hex(dev_id)) + "-" + str(channel)

    # check if we already planned to import a configuration for this device (i.e. another channel)
    device_found = None
    for device in enocean_devices_to_add:
        if device.get(CONF_ENOCEAN_DEVICE_ID, "") == dev_id_string:
            # check if the previously added device has too few channels
            eep = device.get(CONF_ENOCEAN_EEP, "")
            planned_channels = 0
            if eep[0:5] != "D2-01":
                break

            eep_type = int(eep[6:8], 16)
            if eep_type == 0x07:
                planned_channels = 1
            elif eep_type == 0x11:
                planned_channels = 2
            elif eep_type == 0x13:
                planned_channels = 4
            elif eep_type == 0x14:
                planned_channels = 8

            if planned_channels < required_channels:
                LOGGER.warning(
                    "Removing EnOcean device %s from scheduled imports list (will be rescheduled with different EEP), planned: %i, required: %i",
                    dev_id_string,
                    planned_channels,
                    required_channels,
                )
                device_found = device
            else:
                device_type = None
            break

    if device_found is not None:
        enocean_devices_to_add.remove(device_found)

    return EnOceanImportConfig(
        new_unique_id=new_unique_id,
        old_unique_id=old_unique_id,
        device_type=device_type,
    )


def _switch_get_required_channels_and_eep(
    channel: int,
) -> tuple[int, EnOceanSupportedDeviceType]:
    if channel == 0:
        return 1, EEP_D2_01_07
    if channel < 2:
        return 2, EEP_D2_01_11
    if channel < 4:
        return 4, EEP_D2_01_13
    # 8 channel device (maximum supported)
    return 8, EEP_D2_01_14


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
                    "Removing Home Assistant device %s and associated entities for unconfigured EnOcean device %s",
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
