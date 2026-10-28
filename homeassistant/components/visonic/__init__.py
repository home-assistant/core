"""Integration for a Visonic PowerMax or PowerMaster Security System."""

import asyncio

from homeassistant.const import CONF_TYPE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    DOMAIN,
    PLATFORMS,
    TRANSLATE_EXCEPTION_AUTHORISATION_FAILURE,
    TRANSLATE_EXCEPTION_INITIAL_CONNECTION_FAILURE,
)
from .coordinator import VisonicCoordinator
from .exceptions import VisonicAuthException, VisonicException
from .identity import redact_panel_identification, resolved_connection_identity
from .visonic_data_types import (
    VisonicConfigEntry,
    VisonicCoordinatorData,
    VisonicPanelData,
)
from .visonic_types import DeviceType

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_terminate_coordinator(coordinator: VisonicCoordinator | None) -> None:
    """Stop the backend and shared coordinator."""
    if coordinator is not None:
        if coordinator.data is not None:
            data = VisonicCoordinatorData(connected=False, mode="stopped")
            coordinator.async_set_updated_data(data)  # stop all activity in the hub
        # Stop the panel connection and stop all library activity
        await coordinator.async_panel_stop()
        # Stop the coordinator
        await coordinator.async_shutdown()


async def async_setup_entry(hass: HomeAssistant, entry: VisonicConfigEntry) -> None:
    """Set up a visonic panel from a config entry. This is the main entry point."""
    title = redact_panel_identification(entry.title, entry.data.get(CONF_PANEL_SERIAL))
    if title != entry.title:
        hass.config_entries.async_update_entry(entry, title=title)

    async def close_connection(coordinator: VisonicCoordinator | None) -> None:
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        await async_terminate_coordinator(coordinator)

    if CONF_TYPE not in entry.data or CONF_PANEL_NUMBER not in entry.data:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="invalid_panel_configuration"
        )

    # Create the identity for this panel and config
    identity = await hass.async_add_executor_job(
        resolved_connection_identity, entry.data
    )

    panel_number = entry.data[CONF_PANEL_NUMBER]
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id == entry.entry_id:
            continue
        if panel_number == other.data.get(CONF_PANEL_NUMBER):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="number_in_config_not_unique",
                translation_placeholders={"ident": "panel", "ref": str(panel_number)},
            )
        # Create the identity for the other panel
        other_identity = await hass.async_add_executor_job(
            resolved_connection_identity, other.data
        )
        if identity is not None and other_identity == identity:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="panel_already_configured"
            )

    if hass.state is not CoreState.running:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="panel_connection_deferred",
        )

    vcd = VisonicPanelData(VisonicCoordinator(hass, entry, panel_number), panel_number)
    entry.runtime_data = vcd

    async def async_stop(_event: Event) -> None:
        """Close the panel connection before shared sessions are closed."""
        await async_terminate_coordinator(vcd.coordinator)

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        if await vcd.coordinator.async_panel_connect():
            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
            )
            return
    except asyncio.CancelledError:
        await close_connection(vcd.coordinator)
        raise
    except VisonicAuthException:
        await close_connection(vcd.coordinator)
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key=TRANSLATE_EXCEPTION_AUTHORISATION_FAILURE,
            translation_placeholders={"panel_id": str(panel_number)},
        ) from None
    except ConfigEntryAuthFailed, ConfigEntryNotReady:
        await close_connection(vcd.coordinator)
        raise
    except VisonicException, TimeoutError, ConnectionError, OSError:
        await close_connection(vcd.coordinator)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key=TRANSLATE_EXCEPTION_INITIAL_CONNECTION_FAILURE,
            translation_placeholders={"panel_id": str(panel_number)},
        ) from None

    await close_connection(vcd.coordinator)
    raise ConfigEntryNotReady(
        translation_domain=DOMAIN,
        translation_key=TRANSLATE_EXCEPTION_INITIAL_CONNECTION_FAILURE,
        translation_placeholders={"panel_id": str(panel_number)},
    )


async def async_unload_entry(hass: HomeAssistant, entry: VisonicConfigEntry) -> None:
    """Unload the alarm platform and stop its panel connection."""
    try:
        DeviceType(entry.data[CONF_TYPE])
    except (KeyError, ValueError) as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="invalid_panel_configuration"
        ) from err

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    vcd = entry.runtime_data
    if not vcd:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="panel_coordinator_missing"
        )
    await async_terminate_coordinator(vcd.coordinator)
