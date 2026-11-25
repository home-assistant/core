"""Support for Automation Device Specification (ADS)."""

import asyncio
from contextlib import suppress
import logging

import probatio
import pyads

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import DATA_ADS, DATA_SETUP_DONE, DOMAIN
from .entity import AdsEntity
from .hub import AdsConfigEntry, connect
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_DEVICE): cv.string,
                probatio.Required(CONF_PORT): probatio.Port(),
                probatio.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component."""
    async_setup_services(hass)
    hass.data[DATA_SETUP_DONE] = asyncio.Event()

    if DOMAIN in config:
        hass.async_create_task(_async_import(hass, config[DOMAIN]))

    return True


async def _async_import(hass: HomeAssistant, conf: ConfigType) -> None:
    """Import the YAML connection config and raise a deprecation issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
    )

    # An already configured entry still means the YAML block can go away.
    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "single_instance_allowed"
    ):
        # The connection and its YAML entities stay unavailable until the user
        # acts, so this is more than a deprecation notice.
        issue_id = f"deprecated_yaml_import_issue_{result['reason']}"
        severity = IssueSeverity.ERROR
    else:
        issue_id = "deprecated_yaml"
        severity = IssueSeverity.WARNING

    async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version="2027.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=severity,
        translation_key=issue_id,
        translation_placeholders={"domain": DOMAIN, "integration_title": "ADS"},
    )


async def async_setup_entry(hass: HomeAssistant, entry: AdsConfigEntry) -> None:
    """Set up ADS from a config entry."""
    try:
        await _async_setup_entry(hass, entry)
    finally:
        hass.data[DATA_SETUP_DONE].set()


async def _async_setup_entry(hass: HomeAssistant, entry: AdsConfigEntry) -> None:
    """Connect, and hand the entities of an earlier setup to the new hub."""
    try:
        hub = await hass.async_add_executor_job(
            connect,
            entry.data[CONF_DEVICE],
            entry.data[CONF_PORT],
            entry.data.get(CONF_IP_ADDRESS),
        )
    except (pyads.ADSError, OSError, RuntimeError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    entry.runtime_data = hub
    hub.async_start_monitoring(hass)

    if previous_hub := hass.data.pop(DATA_ADS, None):
        # The previous hub stays the entities' registry while the entry is
        # unloaded, so entities removed in the meantime are already gone here.
        devices = previous_hub.devices
        # Rebind synchronously so a concurrent reload sees every device on the
        # new hub, then resubscribe in the background since each one can wait
        # up to 10s for its first value.
        for device in devices:
            device.rebind(hub)

        async def _async_resubscribe_device(device: AdsEntity) -> None:
            try:
                await device.async_added_to_hass()
            except Exception:
                _LOGGER.exception("Error resubscribing %s", device.entity_id)

        async def _async_resubscribe_devices() -> None:
            # A symbol the PLC never answers must not hold up the rest.
            await asyncio.gather(*(_async_resubscribe_device(d) for d in devices))

        hub.resubscribe_task = entry.async_create_task(
            hass, _async_resubscribe_devices(), "ads resubscribe devices"
        )

    async def _async_shutdown(event: Event) -> None:
        hub.async_stop_monitoring()
        await hass.async_add_executor_job(hub.shutdown)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_shutdown)
    )


async def async_unload_entry(hass: HomeAssistant, entry: AdsConfigEntry) -> None:
    """Unload an ADS config entry."""
    hub = entry.runtime_data
    hub.async_stop_monitoring()
    # Entry tasks are only cancelled once this returns, so the resubscribe task
    # has to be stopped here or it would add notifications back during shutdown.
    if task := hub.resubscribe_task:
        hub.resubscribe_task = None
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    # Keep the hub as the registry for the YAML entities that outlive the entry.
    hass.data[DATA_ADS] = hub
    await hass.async_add_executor_job(hub.shutdown)
