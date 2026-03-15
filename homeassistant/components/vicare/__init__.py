"""The ViCare integration."""

from __future__ import annotations

from contextlib import suppress
import logging
import os

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.storage import STORAGE_DIR

from .api import ConfigEntryAuth
from .const import (
    DEFAULT_CACHE_DURATION,
    DOMAIN,
    PLATFORMS,
    UNSUPPORTED_DEVICES,
    VICARE_TOKEN_FILENAME,
)
from .types import ViCareConfigEntry, ViCareData, ViCareDevice
from .utils import get_device, get_device_serial

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ViCareConfigEntry) -> bool:
    """Migrate old config entry to OAuth2."""
    if entry.version == 1 and entry.minor_version == 1:
        _LOGGER.debug(
            "Migrating ViCare config entry from version %s.%s to 1.2",
            entry.version,
            entry.minor_version,
        )

        # Import the old client_id as an application credential
        if "client_id" in entry.data:
            await async_import_client_credential(
                hass,
                DOMAIN,
                ClientCredential(
                    entry.data["client_id"],
                    "",
                    entry.data.get("username"),
                ),
            )

        # Remove old token file
        with suppress(FileNotFoundError):
            await hass.async_add_executor_job(
                os.remove, hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME)
            )

        # Update entry to new format — user must re-authenticate via OAuth
        hass.config_entries.async_update_entry(
            entry,
            minor_version=2,
            data={
                "auth_implementation": DOMAIN,
                "token": {},
                "heating_type": entry.data.get("heating_type", "auto"),
            },
        )
        _LOGGER.debug("Migration to version 1.2 successful")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ViCareConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    # After migration, token is empty — trigger reauth
    if not entry.data.get("token"):
        raise ConfigEntryAuthFailed("Re-authentication required after migration")

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth = ConfigEntryAuth(hass, session)

    try:
        vicare_data = await hass.async_add_executor_job(setup_vicare_api, entry, auth)
    except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError) as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err

    entry.runtime_data = vicare_data

    for device in entry.runtime_data.devices:
        await async_migrate_devices_and_entities(hass, entry, device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def setup_vicare_api(
    entry: ViCareConfigEntry,
    auth: ConfigEntryAuth,
    cache_duration: int = DEFAULT_CACHE_DURATION,
) -> ViCareData:
    """Set up PyVicare API."""
    client = _login(auth, cache_duration)

    device_config_list = get_supported_devices(client.devices)

    # Increase cache duration to fit rate limit to number of devices
    if (number_of_devices := len(device_config_list)) > 1:
        cache_duration = DEFAULT_CACHE_DURATION * number_of_devices
        _LOGGER.debug(
            "Found %s devices, adjusting cache duration to %s",
            number_of_devices,
            cache_duration,
        )
        client = _login(auth, cache_duration)
        device_config_list = get_supported_devices(client.devices)

    for device in device_config_list:
        _LOGGER.debug(
            "Found device: %s (online: %s)",
            device.getModel(),
            str(device.isOnline()),
        )

    devices = [
        ViCareDevice(config=device_config, api=get_device(entry, device_config))
        for device_config in device_config_list
        if bool(device_config.isOnline())
    ]
    return ViCareData(client=client, devices=devices)


def _login(
    auth: ConfigEntryAuth,
    cache_duration: int = DEFAULT_CACHE_DURATION,
) -> PyViCare:
    """Login via PyViCare API using external OAuth."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(cache_duration)
    vicare_api.initWithExternalOAuth(auth)
    return vicare_api


async def async_unload_entry(hass: HomeAssistant, entry: ViCareConfigEntry) -> bool:
    """Unload ViCare config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_devices_and_entities(
    hass: HomeAssistant, entry: ViCareConfigEntry, device: ViCareDevice
) -> None:
    """Migrate old entry."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    gateway_serial: str = device.config.getConfig().serial
    device_id = device.config.getId()
    device_serial: str | None = await hass.async_add_executor_job(
        get_device_serial, device.api
    )
    device_model = device.config.getModel()

    old_identifier = gateway_serial
    new_identifier = (
        f"{gateway_serial}_{device_serial if device_serial is not None else device_id}"
    )

    # Migrate devices
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if (
            device_entry.identifiers == {(DOMAIN, old_identifier)}
            and device_entry.model == device_model
        ):
            _LOGGER.debug(
                "Migrating device %s to new identifier %s",
                device_entry.name,
                new_identifier,
            )
            device_registry.async_update_device(
                device_entry.id,
                serial_number=device_serial,
                new_identifiers={(DOMAIN, new_identifier)},
            )

            # Migrate entities
            for entity_entry in er.async_entries_for_device(
                entity_registry, device_entry.id, True
            ):
                if entity_entry.unique_id.startswith(new_identifier):
                    # already correct, nothing to do
                    continue
                unique_id_parts = entity_entry.unique_id.split("-")
                # replace old prefix `<gateway-serial>`
                # with `<gateways-serial>_<device-serial>`
                unique_id_parts[0] = new_identifier
                # convert climate entity unique id
                # from `<device_identifier>-<circuit_no>`
                # to `<device_identifier>-heating-<circuit_no>`
                if entity_entry.domain == CLIMATE_DOMAIN:
                    unique_id_parts[len(unique_id_parts) - 1] = (
                        f"{entity_entry.translation_key}-"
                        f"{unique_id_parts[len(unique_id_parts) - 1]}"
                    )
                entity_new_unique_id = "-".join(unique_id_parts)

                _LOGGER.debug(
                    "Migrating entity %s to new unique id %s",
                    entity_entry.name,
                    entity_new_unique_id,
                )
                entity_registry.async_update_entity(
                    entity_id=entity_entry.entity_id,
                    new_unique_id=entity_new_unique_id,
                )


def get_supported_devices(
    devices: list[PyViCareDeviceConfig],
) -> list[PyViCareDeviceConfig]:
    """Remove unsupported devices from the list."""
    return [
        device_config
        for device_config in devices
        if device_config.getModel() not in UNSUPPORTED_DEVICES
    ]
