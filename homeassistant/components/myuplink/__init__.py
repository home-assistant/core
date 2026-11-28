"""The myUplink integration."""

from http import HTTPStatus
import logging

from aiohttp import ClientError, ClientResponseError
import jwt
from myuplink import MyUplinkAPI, get_manufacturer, get_model, get_system_name

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import AnyDeviceEntry
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth
from .const import DOMAIN, OAUTH2_SCOPES
from .coordinator import MyUplinkConfigEntry, MyUplinkDataCoordinator
from .helpers import find_matching_platform, was_sensor_before_zero_limits
from .number import get_description as get_number_description
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

# Settings that used to be sensors keep their sensor until this release
DEPRECATED_SETTING_SENSORS_BREAK_IN = "2027.7.0"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MyUplinkConfigEntry
) -> None:
    """Set up myUplink from a config entry."""

    implementation = await async_get_config_entry_implementation(hass, config_entry)

    session = OAuth2Session(hass, config_entry, implementation)
    auth = AsyncConfigEntryAuth(async_get_clientsession(hass), session)

    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if err.status in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="config_entry_auth_failed",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
        ) from err
    except ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
        ) from err

    if set(config_entry.data["token"]["scope"].split(" ")) != set(OAUTH2_SCOPES):
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="incorrect_oauth2_scope",
        )

    # Setup MyUplinkAPI and coordinator for data fetch
    api = MyUplinkAPI(auth)
    coordinator = MyUplinkDataCoordinator(hass, config_entry, api)
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator

    # Update device registry
    create_devices(hass, config_entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    @callback
    def _async_check_on_start(hass: HomeAssistant) -> None:
        _async_check_deprecated_setting_sensors(hass, config_entry)

    async_at_started(hass, _async_check_on_start)


async def async_unload_entry(hass: HomeAssistant, entry: MyUplinkConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


@callback
def create_devices(
    hass: HomeAssistant,
    config_entry: MyUplinkConfigEntry,
    coordinator: MyUplinkDataCoordinator,
) -> None:
    """Update all devices."""
    device_registry = dr.async_get(hass)

    for system in coordinator.data.systems:
        devices_in_system = [x.id for x in system.devices]
        for device_id, device in coordinator.data.devices.items():
            if device_id in devices_in_system:
                device_registry.async_get_or_create(
                    config_entry_id=config_entry.entry_id,
                    identifiers={(DOMAIN, device_id)},
                    name=get_system_name(system),
                    manufacturer=get_manufacturer(device),
                    model=get_model(device),
                    sw_version=device.firmwareCurrent,
                    serial_number=device.product_serial_number,
                )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: MyUplinkConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Remove myuplink config entry from a device."""

    myuplink_data = config_entry.runtime_data
    return not device_entry.identifiers.intersection(
        (DOMAIN, device_id) for device_id in myuplink_data.data.devices
    )


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: MyUplinkConfigEntry
) -> None:
    """Migrate old entry."""

    # Use sub(ject) from access_token as unique_id
    if config_entry.version == 1 and config_entry.minor_version == 1:
        token = jwt.decode(
            config_entry.data["token"]["access_token"],
            options={"verify_signature": False},
        )
        uid = token["sub"]
        hass.config_entries.async_update_entry(
            config_entry, unique_id=uid, minor_version=2
        )
        _LOGGER.info(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )


@callback
def _async_check_deprecated_setting_sensors(
    hass: HomeAssistant, config_entry: MyUplinkConfigEntry
) -> None:
    """Raise a repair issue for each deprecated setting sensor still in use."""
    entity_registry = er.async_get(hass)
    for device_id, point_data in config_entry.runtime_data.data.points.items():
        for point_id, device_point in point_data.items():
            description = get_number_description(device_point)
            if not was_sensor_before_zero_limits(device_point, description):
                continue
            unique_id = f"{device_id}-{point_id}"
            if not (
                entity_id := entity_registry.async_get_entity_id(
                    Platform.SENSOR, DOMAIN, unique_id
                )
            ):
                continue
            issue_id = f"deprecated_setting_sensor_{entity_id}"
            entity_entry = entity_registry.async_get(entity_id)
            automations = automations_with_entity(hass, entity_id)
            scripts = scripts_with_entity(hass, entity_id)
            replacement_entity_id = entity_registry.async_get_entity_id(
                find_matching_platform(device_point, description), DOMAIN, unique_id
            )
            if (
                entity_entry is None
                or entity_entry.disabled
                or replacement_entity_id is None
                or not (automations or scripts)
            ):
                ir.async_delete_issue(hass, DOMAIN, issue_id)
                continue

            items = []
            for domain, used_by in (("automation", automations), ("script", scripts)):
                for item_id in used_by:
                    if item := entity_registry.async_get(item_id):
                        items.append(
                            f"- [{item.name or item.original_name or item_id}]"
                            f"(/config/{domain}/edit/{item.unique_id})"
                        )
                    else:
                        items.append(f"- {item_id}")

            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                breaks_in_ha_version=DEPRECATED_SETTING_SENSORS_BREAK_IN,
                config_entry_id=config_entry.entry_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_setting_sensor",
                translation_placeholders={
                    "entity_id": entity_id,
                    "entity_name": entity_entry.name
                    or entity_entry.original_name
                    or entity_id,
                    "replacement_entity_id": replacement_entity_id,
                    "items": "\n".join(items),
                },
            )
