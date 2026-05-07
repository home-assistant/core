"""The ViCare integration."""

from contextlib import suppress
import logging
import os

from aiohttp import ClientError
from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareOAuthManager import obtain_token_via_basic_auth_pkce
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.config_entry_oauth2_flow import MY_AUTH_CALLBACK_PATH
from homeassistant.helpers.storage import STORAGE_DIR

from .api import ConfigEntryAuth
from .const import (
    DEFAULT_CACHE_DURATION,
    DOMAIN,
    PLATFORMS,
    UNSUPPORTED_DEVICES,
    VICARE_TOKEN_FILENAME,
    VIESSMANN_DEVELOPER_PORTAL,
)
from .types import ViCareConfigEntry, ViCareData, ViCareDevice
from .utils import get_device_serial

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ViCareConfigEntry
) -> bool:
    """Migrate old entry."""
    if config_entry.version > 2:
        return False

    if config_entry.version == 1 and config_entry.minor_version < 2:
        _LOGGER.debug("Migrating ViCare config entry from version 1.1 to 1.2")
        data = {**config_entry.data}
        data.pop("heating_type", None)
        hass.config_entries.async_update_entry(config_entry, data=data, minor_version=2)
        _LOGGER.debug("Migration to version 1.2 successful")

    if config_entry.version == 1 and config_entry.minor_version < 3:
        _LOGGER.debug("Migrating ViCare config entry from version 1.2 to 2.1")
        data = {**config_entry.data}

        client_id = data[CONF_CLIENT_ID]
        username = data[CONF_USERNAME]
        password = data[CONF_PASSWORD]

        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(client_id, "", username),
        )
        _LOGGER.debug("Imported configured client_id as application credential")

        token = await hass.async_add_executor_job(
            obtain_token_via_basic_auth_pkce, client_id, username, password
        )

        data.pop(CONF_USERNAME)
        data.pop(CONF_PASSWORD)
        data.pop(CONF_CLIENT_ID)

        data["auth_implementation"] = DOMAIN
        data[CONF_TOKEN] = token

        token_path = hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME)
        await hass.async_add_executor_job(_remove_token_file, token_path)

        hass.config_entries.async_update_entry(
            config_entry, data=data, version=2, minor_version=1
        )
        if token:
            _LOGGER.debug("Migration to version 2.1 successful (token obtained)")
        else:
            _LOGGER.warning(
                "Migration to version 2.1 complete but token could not be "
                "obtained — re-authentication will be required"
            )

        ir.async_create_issue(
            hass,
            DOMAIN,
            "update_redirect_uri",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="update_redirect_uri",
            translation_placeholders={
                "viessmann_developer_portal": VIESSMANN_DEVELOPER_PORTAL,
                "redirect_url": MY_AUTH_CALLBACK_PATH,
            },
        )

    if config_entry.version == 1 and config_entry.minor_version == 3:
        # Pre-merge testers were on transient v1.3; promote to v2.1 without re-running.
        hass.config_entries.async_update_entry(config_entry, version=2, minor_version=1)
        _LOGGER.debug("Promoted pre-merge ViCare config entry from 1.3 to 2.1")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ViCareConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except (
        config_entry_oauth2_flow.ImplementationUnavailableError,
        ValueError,
    ) as err:
        # Application Credentials missing or removed — user must re-authenticate
        _LOGGER.debug("OAuth2 implementation unavailable: %s", err)
        raise ConfigEntryAuthFailed(
            "OAuth2 implementation unavailable, please re-authenticate"
        ) from err

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await oauth_session.async_ensure_token_valid()
    except OAuth2TokenRequestTransientError as err:
        _LOGGER.debug("OAuth2 token refresh failed (transient): %s", err)
        raise ConfigEntryNotReady("Transient error refreshing OAuth2 token") from err
    except (OAuth2TokenRequestReauthError, OAuth2TokenRequestError, KeyError) as err:
        _LOGGER.debug("OAuth2 token validation failed (auth): %s", err)
        raise ConfigEntryAuthFailed(
            "OAuth2 token is invalid, please re-authenticate"
        ) from err
    except ClientError as err:
        _LOGGER.debug("OAuth2 token validation failed (transient): %s", err)
        raise ConfigEntryNotReady("Unable to reach Viessmann auth server") from err

    auth = ConfigEntryAuth(hass, oauth_session)

    try:
        entry.runtime_data = await hass.async_add_executor_job(_setup_vicare_api, auth)
    except (
        PyViCareInvalidConfigurationError,
        PyViCareInvalidCredentialsError,
    ) as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err

    for device in entry.runtime_data.devices:
        # Migration can be removed in 2025.4.0
        await async_migrate_devices_and_entities(hass, entry, device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _remove_token_file(token_path: str) -> None:
    """Remove legacy token file if it exists."""
    with suppress(FileNotFoundError):
        os.remove(token_path)


def _setup_vicare_api(
    auth: ConfigEntryAuth,
    cache_duration: int = DEFAULT_CACHE_DURATION,
) -> ViCareData:
    """Set up PyVicare API."""
    client = PyViCare()
    client.setCacheDuration(cache_duration)
    client.initWithExternalOAuth(auth)

    device_config_list = get_supported_devices(client.devices)

    # increase cache duration to fit rate limit to number of devices
    if (number_of_devices := len(device_config_list)) > 1:
        cache_duration = DEFAULT_CACHE_DURATION * number_of_devices
        _LOGGER.debug(
            "Found %s devices, adjusting cache duration to %s",
            number_of_devices,
            cache_duration,
        )
        client = PyViCare()
        client.setCacheDuration(cache_duration)
        client.initWithExternalOAuth(auth)
        device_config_list = get_supported_devices(client.devices)

    for device in device_config_list:
        _LOGGER.debug(
            "Found device: %s (online: %s)",
            device.getModel(),
            str(device.isOnline()),
        )

    devices = [
        ViCareDevice(config=device_config, api=device_config.asAutoDetectDevice())
        for device_config in device_config_list
        if bool(device_config.isOnline())
    ]
    return ViCareData(client=client, devices=devices)


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
