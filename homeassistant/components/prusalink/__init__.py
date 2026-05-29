"""The PrusaLink integration."""

from httpx import ConnectError, HTTPError, InvalidURL
from pyprusalink import PrusaLink
from pyprusalink.types import InvalidAuth, PrusaLinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.httpx_client import get_async_client

from .config_flow import PrusaLinkConfigFlow
from .const import DOMAIN
from .coordinator import (
    InfoUpdateCoordinator,
    JobUpdateCoordinator,
    LegacyStatusCoordinator,
    PrusaLinkConfigEntry,
    PrusaLinkUpdateCoordinator,
    StatusCoordinator,
    VersionUpdateCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: PrusaLinkConfigEntry) -> bool:
    """Set up PrusaLink from a config entry."""
    if entry.version == 1 and entry.minor_version < 2:
        raise ConfigEntryError("Please upgrade your printer's firmware.")

    api = PrusaLink(
        get_async_client(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinators: dict[str, PrusaLinkUpdateCoordinator] = {
        "legacy_status": LegacyStatusCoordinator(hass, entry, api),
        "status": StatusCoordinator(hass, entry, api),
        "job": JobUpdateCoordinator(hass, entry, api),
        "info": InfoUpdateCoordinator(hass, entry, api),
        "version": VersionUpdateCoordinator(hass, entry, api),
    }
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if (config_entry.version, config_entry.minor_version) > (
        PrusaLinkConfigFlow.VERSION,
        PrusaLinkConfigFlow.MINOR_VERSION,
    ):
        # This means the user has downgraded from a future version
        return False

    new_data = dict(config_entry.data)
    if config_entry.version == 1:
        serial: str | None = config_entry.unique_id
        update_data: dict[str, object] = {}

        if config_entry.minor_version < 2:
            # Add username and password
            # "maker" is currently hardcoded in the firmware
            # https://github.com/prusa3d/Prusa-Firmware-Buddy/blob/bfb0ffc745ee6546e7efdba618d0e7c0f4c909cd/lib/WUI/wui_api.h#L19
            username = "maker"
            password = config_entry.data[CONF_API_KEY]

            api = PrusaLink(
                get_async_client(hass),
                config_entry.data[CONF_HOST],
                username,
                password,
            )
            try:
                info = await api.get_info()
            except InvalidAuth:
                # We are unable to reach the new API which usually means
                # that the user is running an outdated firmware version
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    "firmware_5_1_required",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="firmware_5_1_required",
                    translation_placeholders={
                        "entry_title": config_entry.title,
                        "prusa_mini_firmware_update": "https://help.prusa3d.com/article/firmware-updating-mini-mini_124784",
                        "prusa_mk4_xl_firmware_update": "https://help.prusa3d.com/article/how-to-update-firmware-mk4-xl_453086",
                    },
                )
                # There is a check in the async_setup_entry to
                # prevent the setup if minor_version < 2
                # Currently we can't reload the config entry
                # if the migration returns False.
                # Return True here to workaround that.
                return True

            serial = info.get("serial")

            new_data[CONF_USERNAME] = username
            new_data[CONF_PASSWORD] = password
            update_data["data"] = new_data
            update_data["minor_version"] = 2

            ir.async_delete_issue(hass, DOMAIN, "firmware_5_1_required")

        if config_entry.minor_version < 3:
            if not serial and CONF_USERNAME in new_data and CONF_PASSWORD in new_data:
                api = PrusaLink(
                    get_async_client(hass),
                    config_entry.data[CONF_HOST],
                    new_data[CONF_USERNAME],
                    new_data[CONF_PASSWORD],
                )
                try:
                    info = await api.get_info()
                except (
                    InvalidAuth,
                    PrusaLinkError,
                    ConnectError,
                    HTTPError,
                    InvalidURL,
                    TimeoutError,
                ):
                    info = None

                if info is not None:
                    serial = info.get("serial")

            if serial:
                old_prefix = f"{config_entry.entry_id}_"
                new_prefix = f"{serial}_"

                entity_registry = er.async_get(hass)
                for entity_entry in er.async_entries_for_config_entry(
                    entity_registry, config_entry.entry_id
                ):
                    if entity_entry.unique_id.startswith(old_prefix):
                        entity_registry.async_update_entity(
                            entity_entry.entity_id,
                            new_unique_id=entity_entry.unique_id.replace(
                                old_prefix, new_prefix, 1
                            ),
                        )

                device_registry = dr.async_get(hass)
                for device_entry in dr.async_entries_for_config_entry(
                    device_registry, config_entry.entry_id
                ):
                    old_identifier = (DOMAIN, config_entry.entry_id)
                    identifiers = set(device_entry.identifiers)
                    if old_identifier not in identifiers:
                        continue

                    identifiers.discard(old_identifier)
                    identifiers.add((DOMAIN, serial))
                    device_registry.async_update_device(
                        device_id=device_entry.id,
                        new_identifiers=identifiers,
                    )
                update_data["minor_version"] = 3
                if not config_entry.unique_id:
                    update_data["unique_id"] = serial

        if update_data:
            hass.config_entries.async_update_entry(config_entry, **update_data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PrusaLinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
