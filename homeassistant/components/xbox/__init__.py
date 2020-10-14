"""The xbox integration."""
import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Dict, Optional

import voluptuous as vol
from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.const import HOME_APP_IDS, SYSTEM_PFN_ID_MAP
from xbox.webapi.api.provider.catalog.models import AlternateIdType, Product
from xbox.webapi.api.provider.smartglass.models import (
    SmartglassConsoleList,
    SmartglassConsoleStatus,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import api, config_flow
from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["media_player", "remote"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the xbox component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up xbox from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    client = XboxLiveClient(auth)
    consoles: SmartglassConsoleList = await client.smartglass.get_console_list()
    _LOGGER.debug(
        "Found %d consoles: %s",
        len(consoles.result),
        consoles.dict(),
    )

    coordinator = XboxUpdateCoordinator(hass, client, consoles)
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": XboxLiveClient(auth),
        "consoles": consoles,
        "coordinator": coordinator,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@dataclass
class XboxData:
    """Xbox dataclass for update coordinator."""

    status: SmartglassConsoleStatus
    app_details: Optional[Product]


class XboxUpdateCoordinator(DataUpdateCoordinator):
    """Store Xbox Console Status."""

    def __init__(
        self,
        hass: HomeAssistantType,
        client: XboxLiveClient,
        consoles: SmartglassConsoleList,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.data: Dict[str, XboxData] = {}
        self.client: XboxLiveClient = client
        self.consoles: SmartglassConsoleList = consoles

    async def _async_update_data(self) -> Dict[str, XboxData]:
        """Fetch the latest console status."""
        new_data: Dict[str, XboxData] = {}
        for console in self.consoles.result:
            current_state: Optional[XboxData] = self.data.get(console.id)
            status: SmartglassConsoleStatus = (
                await self.client.smartglass.get_console_status(console.id)
            )

            _LOGGER.debug(
                "%s status: %s",
                console.name,
                status.dict(),
            )

            # Setup focus app
            app_details: Optional[Product] = None
            if current_state is not None:
                app_details = current_state.app_details

            if status.focus_app_aumid:
                if (
                    not current_state
                    or status.focus_app_aumid != current_state.status.focus_app_aumid
                ):
                    app_id = status.focus_app_aumid.split("!")[0]
                    id_type = AlternateIdType.PACKAGE_FAMILY_NAME
                    if app_id in SYSTEM_PFN_ID_MAP:
                        id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
                        app_id = SYSTEM_PFN_ID_MAP[app_id][id_type]
                    catalog_result = (
                        await self.client.catalog.get_product_from_alternate_id(
                            app_id, id_type
                        )
                    )
                    if catalog_result and catalog_result.products:
                        app_details = catalog_result.products[0]
            else:
                if not current_state or not current_state.status.focus_app_aumid:
                    id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
                    catalog_result = (
                        await self.client.catalog.get_product_from_alternate_id(
                            HOME_APP_IDS[id_type], id_type
                        )
                    )
                    app_details = catalog_result.products[0]

            new_data[console.id] = XboxData(status=status, app_details=app_details)

        return new_data
