"""Support for the Philips Hue system."""

from aiohue.util import normalize_bridge_id
from aiohue.v1 import HueBridgeV1
from aiohue.v2 import HueBridgeV2

from homeassistant import config_entries, core
from homeassistant.components import persistent_notification
from homeassistant.const import CONF_API_KEY, CONF_USERNAME
from homeassistant.helpers import device_registry as dr

from .bridge import HueBridge
from .const import CONF_USE_V2, DOMAIN, SERVICE_HUE_ACTIVATE_SCENE
from .services import LOGGER, async_register_services


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up a bridge from a config entry."""
    # migrate CONF_USERNAME --> CONF_API_KEY
    if CONF_USERNAME in entry.data:
        data = dict(entry.data)
        data[CONF_API_KEY] = data.pop(CONF_USERNAME)
        hass.config_entries.async_update_entry(entry, data=data)
    # migrate V1 -> V2
    if CONF_USE_V2 not in entry.data:
        LOGGER.info("V2 migration should be triggered!")

    # setup the bridge instance
    bridge = HueBridge(hass, entry)
    if not await bridge.async_setup():
        return False

    # register HUE services
    await async_register_services(hass)

    api: HueBridgeV1 | HueBridgeV2 = bridge.api

    # For backwards compat
    unique_id = normalize_bridge_id(api.config.bridge_id)
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=unique_id)

    # For recovering from bug where we incorrectly assumed homekit ID = bridge ID
    elif entry.unique_id != unique_id:
        # Find entries with this unique ID
        other_entry = next(
            (
                entry
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.unique_id == unique_id
            ),
            None,
        )

        if other_entry is None:
            # If no other entry, update unique ID of this entry ID.
            hass.config_entries.async_update_entry(entry, unique_id=unique_id)

        elif other_entry.source == config_entries.SOURCE_IGNORE:
            # There is another entry but it is ignored, delete that one and update this one
            hass.async_create_task(
                hass.config_entries.async_remove(other_entry.entry_id)
            )
            hass.config_entries.async_update_entry(entry, unique_id=unique_id)
        else:
            # There is another entry that already has the right unique ID. Delete this entry
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
            return False

    # add bridge device to device registry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, api.config.mac_address)},
        identifiers={(DOMAIN, api.config.bridge_id)},
        manufacturer="Signify",
        name=api.config.name,
        model=api.config.model_id,
        sw_version=api.config.software_version,
    )

    if (
        not bridge.use_v2
        and api.config.model_id == "BSB002"
        and api.config.software_version < "1935144040"
    ):
        persistent_notification.async_create(
            hass,
            "Your Hue hub has a known security vulnerability ([CVE-2020-6007](https://cve.circl.lu/cve/CVE-2020-6007)). Go to the Hue app and check for software updates.",
            "Signify Hue",
            "hue_hub_firmware",
        )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    unload_success = await hass.data[DOMAIN][entry.entry_id].async_reset()
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
        hass.services.async_remove(DOMAIN, SERVICE_HUE_ACTIVATE_SCENE)
    return unload_success
