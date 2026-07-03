"""Support for Proxmox VE."""

import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    AUTH_OTHER,
    AUTH_PAM,
    AUTH_PVE,
    CONF_AUTH_METHOD,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_TOKEN_ID,
    CONF_TOKEN_SECRET,
    CONF_VMS,
    DEFAULT_PORT,
    DEFAULT_REALM,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Optional(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Required(
                            CONF_AUTH_METHOD, default=DEFAULT_REALM
                        ): cv.string,
                        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
                        vol.Optional(CONF_TOKEN, default=False): cv.boolean,
                        vol.Optional(CONF_TOKEN_ID): cv.string,
                        vol.Optional(CONF_TOKEN_SECRET): cv.string,
                        vol.Optional(
                            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                        ): cv.boolean,
                        vol.Required(CONF_NODES): vol.All(
                            cv.ensure_list,
                            [
                                vol.Schema(
                                    {
                                        vol.Required(CONF_NODE): cv.string,
                                        vol.Optional(CONF_VMS, default=[]): [
                                            cv.positive_int
                                        ],
                                        vol.Optional(CONF_CONTAINERS, default=[]): [
                                            cv.positive_int
                                        ],
                                    }
                                )
                            ],
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Set up a ProxmoxVE from a config entry."""
    coordinator = ProxmoxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Migrate old config entries."""

    # Migration for only the old binary sensors to new unique_id format
    if entry.version < 2:
        ent_reg = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            new_unique_id = (
                f"{entry.entry_id}_{entity_entry.unique_id.split('_')[-2]}_status"
            )

            _LOGGER.debug(
                "Migrating entity %s from old unique_id %s to new unique_id %s",
                entity_entry.entity_id,
                entity_entry.unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )

        hass.config_entries.async_update_entry(entry, version=2)

    # Migration for additional configuration options added to support API tokens
    if entry.version < 3:
        data = dict(entry.data)
        # If CONF_REALM wasn't there yet, extract from username
        if CONF_REALM not in data:
            data[CONF_REALM] = DEFAULT_REALM
            if "@" in data.get(CONF_USERNAME, ""):
                username, realm = data[CONF_USERNAME].split("@", 1)
                data[CONF_USERNAME] = username
                data[CONF_REALM] = realm.lower()

        realm = data[CONF_REALM].lower()

        # If the realm is one of the base providers,
        # set the provider to match the realm.
        data[CONF_AUTH_METHOD] = realm if realm in (AUTH_PAM, AUTH_PVE) else AUTH_OTHER
        data.setdefault(CONF_TOKEN, False)

        hass.config_entries.async_update_entry(entry, data=data, version=3)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ProxmoxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
