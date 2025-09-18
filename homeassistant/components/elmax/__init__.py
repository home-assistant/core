"""The elmax-cloud integration."""

from __future__ import annotations

from elmax_api.exceptions import ElmaxBadLoginError
from elmax_api.http import Elmax, ElmaxLocal, GenericElmax
from elmax_api.model.panel import PanelEntry

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .common import DirectPanel, build_direct_ssl_context, get_direct_api_url
from .const import (
    CONF_ELMAX_MODE,
    CONF_ELMAX_MODE_CLOUD,
    CONF_ELMAX_MODE_DIRECT,
    CONF_ELMAX_MODE_DIRECT_HOST,
    CONF_ELMAX_MODE_DIRECT_PORT,
    CONF_ELMAX_MODE_DIRECT_SSL,
    CONF_ELMAX_MODE_DIRECT_SSL_CERT,
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    ELMAX_PLATFORMS,
)
from .coordinator import ElmaxConfigEntry, ElmaxCoordinator


async def _load_elmax_panel_client(
    entry: ElmaxConfigEntry,
) -> tuple[GenericElmax, PanelEntry]:
    # Connection mode was not present in initial version, default to cloud if not set
    mode = entry.data.get(CONF_ELMAX_MODE, CONF_ELMAX_MODE_CLOUD)
    if mode == CONF_ELMAX_MODE_DIRECT:
        client_api_url = get_direct_api_url(
            host=entry.data[CONF_ELMAX_MODE_DIRECT_HOST],
            port=entry.data[CONF_ELMAX_MODE_DIRECT_PORT],
            use_ssl=entry.data[CONF_ELMAX_MODE_DIRECT_SSL],
        )
        custom_ssl_context = None
        custom_ssl_cert = entry.data.get(CONF_ELMAX_MODE_DIRECT_SSL_CERT)
        if custom_ssl_cert:
            custom_ssl_context = build_direct_ssl_context(cadata=custom_ssl_cert)

        client = ElmaxLocal(
            panel_api_url=client_api_url,
            panel_code=entry.data[CONF_ELMAX_PANEL_PIN],
            ssl_context=custom_ssl_context,
        )
        panel = DirectPanel(panel_uri=client_api_url)
    else:
        client = Elmax(
            username=entry.data[CONF_ELMAX_USERNAME],
            password=entry.data[CONF_ELMAX_PASSWORD],
        )
        client.set_current_panel(
            entry.data[CONF_ELMAX_PANEL_ID], entry.data[CONF_ELMAX_PANEL_PIN]
        )
        # Make sure the panel is online and assigned to the current user
        panel = await _check_cloud_panel_status(client, entry.data[CONF_ELMAX_PANEL_ID])

    return client, panel


async def _check_cloud_panel_status(client: Elmax, panel_id: str) -> PanelEntry:
    """Perform integrity checks against the cloud for panel-user association."""
    # Retrieve the panel online status first
    panels = await client.list_control_panels()
    panel = next((panel for panel in panels if panel.hash == panel_id), None)

    # If the panel is no longer available within the ones associated to that client, raise
    # a config error as the user must reconfigure it in order to  make it work again
    if not panel:
        raise ConfigEntryAuthFailed(
            f"Panel ID {panel_id} is no longer linked to this user account"
        )
    return panel


async def async_setup_entry(hass: HomeAssistant, entry: ElmaxConfigEntry) -> bool:
    """Set up elmax-cloud from a config entry."""
    try:
        client, panel = await _load_elmax_panel_client(entry)
    except ElmaxBadLoginError as err:
        raise ConfigEntryAuthFailed from err

    # Create the API client object and attempt a login, so that we immediately know
    # if there is something wrong with user credentials
    coordinator = ElmaxCoordinator(
        hass=hass,
        entry=entry,
        elmax_api_client=client,
        panel=panel,
    )

    async def _async_on_hass_stop(_: Event) -> None:
        """Close connection when hass stops."""
        await coordinator.async_shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_hass_stop)
    )

    # Issue a first refresh, so that we trigger a re-auth flow if necessary
    await coordinator.async_config_entry_first_refresh()

    # Store a global reference to the coordinator for later use
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Perform platform initialization.
    await hass.config_entries.async_forward_entry_setups(entry, ELMAX_PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ElmaxConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ElmaxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ELMAX_PLATFORMS)
