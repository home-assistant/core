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
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ADS_VAR, CONF_LOCAL_NET_ID, DOMAIN, AdsType
from .entity import AdsEntity
from .hub import AdsConfigEntry, apply_local_net_id, connect

_LOGGER = logging.getLogger(__name__)

ADS_TYPEMAP = {
    AdsType.BOOL: pyads.PLCTYPE_BOOL,
    AdsType.BYTE: pyads.PLCTYPE_BYTE,
    AdsType.INT: pyads.PLCTYPE_INT,
    AdsType.UINT: pyads.PLCTYPE_UINT,
    AdsType.SINT: pyads.PLCTYPE_SINT,
    AdsType.USINT: pyads.PLCTYPE_USINT,
    AdsType.DINT: pyads.PLCTYPE_DINT,
    AdsType.UDINT: pyads.PLCTYPE_UDINT,
    AdsType.WORD: pyads.PLCTYPE_WORD,
    AdsType.DWORD: pyads.PLCTYPE_DWORD,
    AdsType.REAL: pyads.PLCTYPE_REAL,
    AdsType.LREAL: pyads.PLCTYPE_LREAL,
    AdsType.STRING: pyads.PLCTYPE_STRING,
    AdsType.TIME: pyads.PLCTYPE_TIME,
    AdsType.DATE: pyads.PLCTYPE_DATE,
    AdsType.DATE_AND_TIME: pyads.PLCTYPE_DT,
    AdsType.TOD: pyads.PLCTYPE_TOD,
}

CONF_ADS_FACTOR = "factor"
CONF_ADS_TYPE = "adstype"
CONF_ADS_VALUE = "value"


SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_DEVICE): cv.string,
                probatio.Required(CONF_PORT): cv.port,
                probatio.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

SCHEMA_SERVICE_WRITE_DATA_BY_NAME = probatio.Schema(
    {
        probatio.Required(CONF_ADS_TYPE): probatio.Coerce(AdsType),
        probatio.Required(CONF_ADS_VALUE): probatio.Coerce(int),
        probatio.Required(CONF_ADS_VAR): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component."""

    async def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        entries: list[AdsConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="not_loaded"
            )

        ads_var: str = call.data[CONF_ADS_VAR]
        ads_type: AdsType = call.data[CONF_ADS_TYPE]
        value: int = call.data[CONF_ADS_VALUE]

        await hass.async_add_executor_job(
            entries[0].runtime_data.write_by_name,
            ads_var,
            value,
            ADS_TYPEMAP[ads_type],
        )

    # Writing an arbitrary PLC variable can change machine configuration or
    # safety-relevant state, so it is restricted to admins.
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )

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
        breaks_in_ha_version="2027.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=severity,
        translation_key=issue_id,
        translation_placeholders={"domain": DOMAIN, "integration_title": "ADS"},
    )


async def async_setup_entry(hass: HomeAssistant, entry: AdsConfigEntry) -> bool:
    """Set up ADS from a config entry."""
    try:
        hub = await hass.async_add_executor_job(
            connect,
            entry.data[CONF_DEVICE],
            entry.data[CONF_PORT],
            entry.data.get(CONF_IP_ADDRESS),
            entry.data.get(CONF_LOCAL_NET_ID),
        )
    except (pyads.ADSError, RuntimeError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    entry.runtime_data = hub

    if previous_hub := hass.data.pop(DOMAIN, None):
        # The previous hub stays the entities' registry while the entry is
        # unloaded, so entities removed in the meantime are already gone here.
        devices = previous_hub.devices
        # Rebind synchronously so a concurrent reload sees every device on the
        # hub, then resubscribe in the background since each one can take
        # up to 10s.
        for device in devices:
            device.rebind(hub)

        async def _async_resubscribe_device(device: AdsEntity) -> None:
            try:
                await device.async_added_to_hass()
            except Exception:
                _LOGGER.exception("Error resubscribing %s", device.entity_id)

        async def _async_resubscribe_devices() -> None:
            # Each subscription waits up to 10s for its first notification, so
            # a symbol the PLC never answers must not hold up the rest.
            await asyncio.gather(*(_async_resubscribe_device(d) for d in devices))

        hub.resubscribe_task = entry.async_create_task(
            hass, _async_resubscribe_devices(), "ads resubscribe devices"
        )

    async def _async_shutdown(event: Event) -> None:
        await hass.async_add_executor_job(hub.shutdown)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdsConfigEntry) -> bool:
    """Unload an ADS config entry."""
    hub = entry.runtime_data
    # Entry tasks are only cancelled once this returns, so the resubscribe task
    # has to be stopped here or it would add notifications back during shutdown.
    if task := hub.resubscribe_task:
        hub.resubscribe_task = None
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    # Keep the hub as the registry for the YAML entities that outlive the entry,
    # so they can be rebound once it is set up again.
    hass.data[DOMAIN] = hub
    await hass.async_add_executor_job(hub.shutdown)
    if entry.data.get(CONF_LOCAL_NET_ID):
        # The override is process-wide, so it must not outlive the connection.
        await hass.async_add_executor_job(apply_local_net_id, None)
    return True
