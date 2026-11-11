"""Support for Velbus devices."""

from enum import StrEnum
import os
import shutil
from typing import TYPE_CHECKING

import probatio

from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector, service
from homeassistant.helpers.storage import STORAGE_DIR

if TYPE_CHECKING:
    from . import VelbusConfigEntry

from .const import DOMAIN


class VelbusService(StrEnum):
    """Store keys for Velbus services."""

    SCAN = "scan"
    SYNC_CLOCK = "sync_clock"
    SET_MEMO_TEXT = "set_memo_text"
    CLEAR_CACHE = "clear_cache"


class VelbusServiceArgument(StrEnum):
    """Store keys for Velbus service arguments."""

    CONFIG_ENTRY = "config_entry"
    MEMO_TEXT = "memo_text"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the velbus services."""

    async def scan(call: ServiceCall) -> None:
        """Handle a scan service call."""
        entry: VelbusConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, call.data[VelbusServiceArgument.CONFIG_ENTRY]
        )
        try:
            await entry.runtime_data.controller.scan()
        except OSError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="scan_failed",
                translation_placeholders={"error": str(exc)},
            ) from exc

    async def syn_clock(call: ServiceCall) -> None:
        """Handle a sync clock service call."""
        entry: VelbusConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, call.data[VelbusServiceArgument.CONFIG_ENTRY]
        )
        try:
            await entry.runtime_data.controller.sync_clock()
        except OSError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sync_clock_failed",
                translation_placeholders={"error": str(exc)},
            ) from exc

    async def set_memo_text(call: ServiceCall) -> None:
        """Handle Memo Text service call."""
        entry: VelbusConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, call.data[VelbusServiceArgument.CONFIG_ENTRY]
        )
        memo_text = call.data[VelbusServiceArgument.MEMO_TEXT]
        address = call.data[CONF_ADDRESS]
        module = entry.runtime_data.controller.get_module(address)
        if not module:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="module_not_found",
                translation_placeholders={"address": str(address)},
            )
        try:
            await module.set_memo_text(memo_text)
        except OSError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_memo_text_failed",
                translation_placeholders={"error": str(exc)},
            ) from exc

    async def clear_cache(call: ServiceCall) -> None:
        """Handle a clear cache service call."""
        entry: VelbusConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, call.data[VelbusServiceArgument.CONFIG_ENTRY]
        )

        address = call.data.get(CONF_ADDRESS)
        cache_path = hass.config.path(
            STORAGE_DIR,
            f"velbuscache-{entry.entry_id}/{address}.p"
            if address
            else f"velbuscache-{entry.entry_id}/",
        )

        def _clear_cache() -> None:
            if address:
                if os.path.exists(cache_path):
                    os.unlink(cache_path)
            elif os.path.isdir(cache_path):
                shutil.rmtree(cache_path)

        try:
            await hass.async_add_executor_job(_clear_cache)
        except OSError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="clear_cache_failed",
                translation_placeholders={"path": cache_path},
            ) from exc
        # call a scan to repopulate
        await scan(call)

    hass.services.async_register(
        DOMAIN,
        VelbusService.SCAN,
        scan,
        probatio.Schema(
            {
                probatio.Required(
                    VelbusServiceArgument.CONFIG_ENTRY
                ): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                )
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        VelbusService.SYNC_CLOCK,
        syn_clock,
        probatio.Schema(
            {
                probatio.Required(
                    VelbusServiceArgument.CONFIG_ENTRY
                ): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                )
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        VelbusService.SET_MEMO_TEXT,
        set_memo_text,
        probatio.Schema(
            {
                probatio.Required(
                    VelbusServiceArgument.CONFIG_ENTRY
                ): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                probatio.Required(CONF_ADDRESS): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=255)
                ),
                probatio.Optional(
                    VelbusServiceArgument.MEMO_TEXT, default=""
                ): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        VelbusService.CLEAR_CACHE,
        clear_cache,
        probatio.Schema(
            {
                probatio.Required(
                    VelbusServiceArgument.CONFIG_ENTRY
                ): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                probatio.Optional(CONF_ADDRESS): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=255)
                ),
            }
        ),
    )
