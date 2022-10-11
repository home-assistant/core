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

    new_unique_ids: list[str]
    old_unique_ids: dict[str, str]
    device_type: EnOceanSupportedDeviceType | None
    device_name: str
    sender_id: str | None

    def __init__(
        self,
        new_unique_ids: list[str],
        old_unique_ids: dict[str, str],
        device_type: EnOceanSupportedDeviceType | None,
        sender_id: str | None,
        device_name: str,
    ) -> None:
        """Create a new EnOcean import configuration."""
        self.new_unique_ids = new_unique_ids
        self.old_unique_ids = old_unique_ids
        self.device_type = device_type
        self.sender_id = sender_id
        self.device_name = device_name


# upcoming code is part of platform import to be deleted in a future version
# map from EnOcean id strings to platform configs
_enocean_platform_configs: dict[str, list[EnOceanPlatformConfig]] = {}


# upcoming code is part of platform import to be deleted in a future version
def register_platform_config_for_migration_to_config_entry(
    platform_config: EnOceanPlatformConfig,
):
    """Register an EnOcean platform configuration for importing it to the config entry."""

    dev_id = platform_config.config.get(CONF_ENOCEAN_DEVICE_ID, None)

    if not dev_id:
        LOGGER.warning(
            "Cannot register platform configuration with no EnOcean id for import"
        )
        return

    device_id = to_hex_string(dev_id).upper()

    if device_id not in _enocean_platform_configs:
        _enocean_platform_configs[device_id] = [platform_config]
    else:
        _enocean_platform_configs[device_id].append(platform_config)


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
    enocean_platform_configs: dict[str, list[EnOceanPlatformConfig]],
) -> bool:
    """Set up the yaml import."""
    enocean_devices_to_add: list[dict[str, str]] = []
    ent_reg = entity_registry.async_get(hass)

    # map from device id (hex) to list of (new) unique_ids
    new_unique_ids: dict[str, list[str]] = {}

    # map from device id (hex) to map from new unique_id to old unique_id
    old_unique_ids: dict[str, dict[str, str]] = {}

    # map from device id (hex) to map from (new) unique_id to old entity
    old_entities: dict[str, dict[str, entity_registry.RegistryEntry]] = {}

    @callback
    def _schedule_yaml_import(_):
        """Schedule platform configuration import 2s after HA is fully started."""
        if not enocean_platform_configs or len(enocean_platform_configs) < 1:
            return
        async_call_later(hass, 2, _import_yaml)

    @callback
    def _import_yaml(_):
        """Import platform configuration to config entry."""
        LOGGER.warning(
            "EnOcean platform configurations were found in your configuration.yaml. Configuring EnOcean via configuration.yaml is deprecated and will be removed in a future release. Now starting automatic import to config entry... "
        )

        # get the unique config_entry and the devices configured in it
        conf_entries = hass.config_entries.async_entries(DOMAIN)
        if not len(conf_entries) == 1:
            LOGGER.warning(
                "Cannot import platform configurations to config entry - no config entry found"
            )
            return
        config_entry = conf_entries[0]

        configured_enocean_devices = deepcopy(
            config_entry.options.get(CONF_ENOCEAN_DEVICES, [])
        )

        # process the enocean platform configs by EnOcean id
        for device_id, configs in enocean_platform_configs.items():
            # skip configured devices
            if _is_configured(
                dev_id_string=device_id,
                configured_enocean_devices=configured_enocean_devices,
            ):
                LOGGER.debug(
                    "Skipping already configured EnOcean device %s",
                    device_id,
                )
                continue

            new_unique_ids[device_id] = []
            old_unique_ids[device_id] = {}
            old_entities[device_id] = {}

            import_config: EnOceanImportConfig = _get_import_config(
                dev_id_string=device_id, platform_configs=configs
            )

            if import_config.device_type is None:
                continue

            new_unique_ids[device_id] = import_config.new_unique_ids
            old_unique_ids[device_id] = import_config.old_unique_ids

            enocean_devices_to_add.append(
                {
                    CONF_ENOCEAN_DEVICE_ID: device_id,
                    CONF_ENOCEAN_EEP: import_config.device_type.eep,
                    CONF_ENOCEAN_MANUFACTURER: import_config.device_type.manufacturer,
                    CONF_ENOCEAN_MODEL: import_config.device_type.model,
                    CONF_ENOCEAN_DEVICE_NAME: import_config.device_name,
                    CONF_ENOCEAN_SENDER_ID: import_config.sender_id,
                }
            )

            LOGGER.debug(
                "Scheduling EnOcean device %s for import as '%s %s' [EEP %s]",
                device_id,
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
        """Remove those new entities for which an old entity exists and set both the new unique_id and a device on the old entity."""
        for device in enocean_devices_to_add:
            device_id = device[CONF_ENOCEAN_DEVICE_ID]
            LOGGER.debug("Updating entities for imported EnOcean device %s", device_id)

            for new_unique_id in new_unique_ids[device_id]:
                old_unique_id = old_unique_ids[device_id][new_unique_id]

                new_entity = _get_entity_for_unique_id(ent_reg, new_unique_id)
                old_entity = _get_entity_for_unique_id(ent_reg, old_unique_id)

                if new_entity is None:
                    LOGGER.warning(
                        "No new entity with unique id '%s' found", new_unique_id
                    )
                    continue

                if old_entity is None:
                    LOGGER.warning(
                        "No old entity with unique id '%s' found", old_unique_id
                    )
                    continue

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
            "Import of EnOcean platform configurations completed. Please delete them from your configuration.yaml and restart Home Assistant"
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _schedule_yaml_import)

    return True


def _is_configured(dev_id_string: str, configured_enocean_devices):
    """Check if an EnOcean device with the given id was already configured."""
    for device in configured_enocean_devices:
        if device[CONF_ENOCEAN_DEVICE_ID] == dev_id_string:
            return True

    return False


def _get_import_config(
    dev_id_string: str,
    platform_configs: list[EnOceanPlatformConfig],
) -> EnOceanImportConfig:
    """Return a list of EnOcean import configurations for the supplied EnOcean platform configurations."""

    # group platform configs by platform
    platform_configs_by_platform: dict[str, list[EnOceanPlatformConfig]] = {}
    for platform_config in platform_configs:
        if platform_config.platform not in platform_configs_by_platform:
            platform_configs_by_platform[platform_config.platform] = [platform_config]
        else:
            platform_configs_by_platform[platform_config.platform].append(
                platform_config
            )

    # iterate platforms
    for platform, configs in platform_configs_by_platform.items():
        if platform == Platform.BINARY_SENSOR.value:
            config = configs[0].config
            device_name = config.get(CONF_ENOCEAN_DEVICE_NAME, "").strip()
            device_class = config.get("device_class", None)

            if len(configs) > 1:
                LOGGER.warning(
                    "Cannot import more than one platform config for 'binary sensor' EnOcean device %s (invalid configuration.yaml). Will use the first platform config with name '%s' and device class '%s'",
                    dev_id_string,
                    device_name,
                    device_class,
                )

            return _get_binary_sensor_import_config(
                dev_id_string=dev_id_string,
                device_name=device_name,
                device_class=device_class,
            )

        if platform == Platform.LIGHT.value:
            config = configs[0].config
            device_name = config.get(CONF_ENOCEAN_DEVICE_NAME, "").strip()
            sender_id = config.get(CONF_ENOCEAN_SENDER_ID, None)

            sender_id_string: str = ""
            if sender_id is not None:
                sender_id_string = to_hex_string(sender_id).upper()

            if len(configs) > 1:
                LOGGER.warning(
                    "Cannot import more than one platform config for 'light' EnOcean device '%s' (invalid configuration.yaml). Will use the first platform config with sender id '%s'",
                    dev_id_string,
                    sender_id_string,
                )

            return _get_light_import_config(
                dev_id_string=dev_id_string,
                sender_id=sender_id_string,
                device_name=device_name,
            )

        if platform == Platform.SWITCH.value:
            return _get_switch_import_config(
                device_id=dev_id_string,
                platform_configs=configs,
            )

    return EnOceanImportConfig(
        new_unique_ids=[],
        old_unique_ids={},
        device_type=None,
        sender_id=None,
        device_name="",
    )


def _get_binary_sensor_import_config(
    dev_id_string: str, device_name: str, device_class: str
) -> EnOceanImportConfig:
    """Return an import config for a binary sensor."""
    dev_id = from_hex_string(dev_id_string)
    new_unique_id = dev_id_string + "-" + Platform.BINARY_SENSOR.value + "-0"

    if device_class is None:
        old_unique_id = str(combine_hex(dev_id)) + "-None"
    else:
        old_unique_id = str(combine_hex(dev_id)) + "-" + device_class

    if device_name == "":
        device_name = "Imported EnOcean binary sensor " + dev_id_string

    return EnOceanImportConfig(
        new_unique_ids=[new_unique_id],
        old_unique_ids={new_unique_id: old_unique_id},
        device_type=EEP_F6_02_01,
        device_name=device_name,
        sender_id="",
    )


def _get_light_import_config(
    dev_id_string: str, device_name: str, sender_id: str
) -> EnOceanImportConfig:
    """Return an import config for a light."""
    dev_id = from_hex_string(dev_id_string)
    new_unique_id = dev_id_string + "-" + Platform.LIGHT.value + "-0"
    old_unique_id = str(combine_hex(dev_id))

    if device_name == "":
        device_name = "Imported EnOcean light " + dev_id_string

    device_type = EnOceanSupportedDeviceType(
        eep="A5-38-08_EltakoFUD61", manufacturer="Eltako", model="FUD61NPN"
    )

    return EnOceanImportConfig(
        new_unique_ids=[new_unique_id],
        old_unique_ids={new_unique_id: old_unique_id},
        device_type=device_type,
        sender_id=sender_id,
        device_name=device_name,
    )


def _get_switch_import_config(
    device_id: str,
    platform_configs: list[EnOceanPlatformConfig],
) -> EnOceanImportConfig:
    """Return an import config for a switch."""
    dev_id = from_hex_string(device_id)

    # 1 channel device
    device_type = EEP_D2_01_07
    max_channel = 0

    new_unique_ids = []
    old_unique_ids = {}

    device_name = ""

    # iterate configs to determine unique ids and required channels
    for platform_config in platform_configs:
        if device_name == "":
            device_name = platform_config.config.get("name", "")

        channel = platform_config.config.get("channel", 0)
        max_channel = max(max_channel, channel)

        new_unique_id = device_id + "-" + Platform.SWITCH.value + "-" + str(channel)
        new_unique_ids.append(new_unique_id)

        old_unique_id = str(combine_hex(dev_id)) + "-" + str(channel)
        old_unique_ids[new_unique_id] = old_unique_id

    if device_name == "":
        device_name = "Imported EnOcean switch " + device_id

    if max_channel < 2:
        device_type = EEP_D2_01_11
    elif max_channel < 4:
        device_type = EEP_D2_01_13
    elif max_channel < 8:
        device_type = EEP_D2_01_14
    else:
        LOGGER.warning(
            "Import of EnOcean switch '%s' will be incomplete: too many channels (%i). Only 1, 2, 4, or 8 channels are supported; importer will configure 8 channels",
            device_id,
            max_channel + 1,
        )
        device_type = EEP_D2_01_14

    return EnOceanImportConfig(
        new_unique_ids=new_unique_ids,
        old_unique_ids=old_unique_ids,
        device_type=device_type,
        device_name=device_name,
        sender_id="",
    )


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

    device_ids = [
        dev["id"].upper() for dev in entry.options.get(CONF_ENOCEAN_DEVICES, [])
    ]

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
