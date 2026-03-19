"""The ViCare integration."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
import logging
import os
from typing import Any

from aiohttp import ClientError
from authlib.common.security import generate_token as generate_code_verifier
from authlib.integrations.requests_client import OAuth2Session
from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareAbstractOAuthManager import (
    AUTHORIZE_URL,
    SCOPE_IOT,
    SCOPE_OFFLINE_ACCESS,
    TOKEN_URL,
)
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareOAuthManager import REDIRECT_URI
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)
import requests

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
)
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
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
from .utils import get_device_serial, login

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ViCareConfigEntry
) -> bool:
    """Migrate old entry."""
    if config_entry.version > 1:
        return False

    if config_entry.version == 1 and config_entry.minor_version < 2:
        _LOGGER.debug("Migrating ViCare config entry from version 1.1 to 1.2")
        data = {**config_entry.data}
        data.pop("heating_type", None)
        hass.config_entries.async_update_entry(config_entry, data=data, minor_version=2)
        _LOGGER.debug("Migration to version 1.2 successful")

    if config_entry.version == 1 and config_entry.minor_version < 3:
        _LOGGER.debug("Migrating ViCare config entry from version 1.2 to 1.3")
        data = {**config_entry.data}

        # Import legacy client_id as application credential
        if client_id := data.get(CONF_CLIENT_ID):
            await async_import_client_credential(
                hass,
                DOMAIN,
                ClientCredential(client_id, "", "Imported legacy credential"),
            )
            _LOGGER.debug("Imported legacy client_id as application credential")

        # Obtain OAuth2 token with refresh_token using existing credentials
        token = {}
        if (
            client_id
            and (username := data.get(CONF_USERNAME))
            and (password := data.get(CONF_PASSWORD))
        ):
            token = await hass.async_add_executor_job(
                _obtain_token_via_password_grant, client_id, username, password
            )

        # Remove legacy auth fields
        data.pop(CONF_USERNAME, None)
        data.pop(CONF_PASSWORD, None)
        data.pop(CONF_CLIENT_ID, None)

        # Set OAuth2 auth implementation
        data["auth_implementation"] = DOMAIN
        data["token"] = token

        # Remove legacy token file
        token_path = hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME)
        await hass.async_add_executor_job(_remove_token_file, token_path)

        hass.config_entries.async_update_entry(config_entry, data=data, minor_version=3)
        if token:
            _LOGGER.debug("Migration to version 1.3 successful (token obtained)")
        else:
            _LOGGER.warning(
                "Migration to version 1.3 complete but token could not be "
                "obtained — re-authentication will be required"
            )

        # Inform user to update redirect URI for future re-authentication
        ir.async_create_issue(
            hass,
            DOMAIN,
            "update_redirect_uri",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="update_redirect_uri",
            translation_placeholders={
                "viessmann_developer_portal": VIESSMANN_DEVELOPER_PORTAL,
            },
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ViCareConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    if "auth_implementation" in entry.data:
        # OAuth2 path
        _LOGGER.debug("Using OAuth2 authentication")
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )
        try:
            await oauth_session.async_ensure_token_valid()
        except (KeyError, OAuth2TokenRequestError) as err:
            _LOGGER.debug("OAuth2 token validation failed (auth): %s", err)
            raise ConfigEntryAuthFailed(
                "OAuth2 token is invalid, please re-authenticate"
            ) from err
        except ClientError as err:
            _LOGGER.debug("OAuth2 token validation failed (transient): %s", err)
            raise ConfigEntryNotReady("Unable to reach Viessmann auth server") from err

        auth = ConfigEntryAuth(hass, oauth_session)

        try:
            entry.runtime_data = await hass.async_add_executor_job(
                _setup_vicare_api, _login_oauth, entry, auth
            )
        except (
            PyViCareInvalidConfigurationError,
            PyViCareInvalidCredentialsError,
        ) as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
    else:
        # Legacy password path (can be removed in 2026.10)
        _LOGGER.debug("Using legacy password authentication")
        try:
            entry.runtime_data = await hass.async_add_executor_job(
                _setup_vicare_api, _login_legacy, hass, entry.data
            )
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


def _obtain_token_via_password_grant(
    client_id: str, username: str, password: str
) -> dict[str, Any]:
    """Obtain an OAuth2 token with refresh_token using password-grant flow.

    Uses the existing credentials to silently obtain a refresh token
    during migration, so users don't need to re-authenticate.
    """
    scope = [SCOPE_IOT, SCOPE_OFFLINE_ACCESS]
    redirect_uri = REDIRECT_URI
    oauth = OAuth2Session(
        client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge_method="S256",
    )
    code_verifier = generate_code_verifier(48)
    auth_url, _ = oauth.create_authorization_url(
        AUTHORIZE_URL, code_verifier=code_verifier
    )

    try:
        response = requests.post(
            auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=(username, password),
            allow_redirects=False,
            timeout=15,
        )
    except requests.RequestException:
        _LOGGER.warning("Failed to reach Viessmann auth server during migration")
        return {}

    if response.status_code != 302 or "Location" not in response.headers:
        _LOGGER.warning("Password-grant authentication failed during migration")
        return {}

    try:
        oauth.fetch_token(
            TOKEN_URL,
            authorization_response=response.headers["Location"],
            code_verifier=code_verifier,
        )
    except requests.RequestException, KeyError, ValueError:
        _LOGGER.warning("Token exchange failed during migration")
        return {}

    token = dict(oauth.token)
    _LOGGER.debug("Obtained OAuth2 token with refresh_token via password grant")
    return token


def _remove_token_file(token_path: str) -> None:
    """Remove legacy token file if it exists."""
    with suppress(FileNotFoundError):
        os.remove(token_path)


def _login_oauth(
    entry: ViCareConfigEntry,
    auth: ConfigEntryAuth,
    cache_duration: int = DEFAULT_CACHE_DURATION,
) -> PyViCare:
    """Login via OAuth2."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(cache_duration)
    vicare_api.initWithExternalOAuth(auth)
    return vicare_api


def _login_legacy(
    hass: HomeAssistant,
    entry_data: Mapping[str, Any],
    cache_duration: int = DEFAULT_CACHE_DURATION,
) -> PyViCare:
    """Login via legacy password."""
    return login(hass, entry_data, cache_duration)


def _setup_vicare_api(
    login_fn: Any,
    *login_args: Any,
) -> ViCareData:
    """Set up PyVicare API."""
    client = login_fn(*login_args)

    device_config_list = get_supported_devices(client.devices)

    # increase cache duration to fit rate limit to number of devices
    if (number_of_devices := len(device_config_list)) > 1:
        cache_duration = DEFAULT_CACHE_DURATION * number_of_devices
        _LOGGER.debug(
            "Found %s devices, adjusting cache duration to %s",
            number_of_devices,
            cache_duration,
        )
        client = login_fn(*login_args, cache_duration=cache_duration)
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
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Only remove token file for legacy entries
    if "auth_implementation" not in entry.data:
        with suppress(FileNotFoundError):
            await hass.async_add_executor_job(
                os.remove, hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME)
            )

    return unload_ok


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
