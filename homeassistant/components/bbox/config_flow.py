"""Config flow for the Bbox integration."""

from collections.abc import Mapping
from typing import Any, override

from aiohttp import CookieJar
from bbox_api import (
    BboxApiError,
    BboxAuthenticationError,
    BboxClient,
    BboxConnectionError,
    BboxRateLimitError,
    BboxTimeoutError,
    DeviceInfo,
)
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN

PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)


def _user_schema(defaults: Mapping[str, Any]) -> probatio.Schema:
    """Return the schema of the step asking for the connection settings."""
    return probatio.Schema(
        {
            probatio.Required(
                CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)
            ): TextSelector(),
            probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR,
            probatio.Optional(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)
            ): BooleanSelector(),
        }
    )


def _reauth_schema(defaults: Mapping[str, Any]) -> probatio.Schema:
    """Return the schema of the reauthentication step."""
    return probatio.Schema(
        {
            probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR,
            probatio.Optional(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)
            ): BooleanSelector(),
        }
    )


async def _async_validate(
    hass: HomeAssistant, host: str, password: str, verify_ssl: bool
) -> tuple[dict[str, str], DeviceInfo | None]:
    """Validate that the Bbox answers and accepts the password.

    The hosts endpoint is used on purpose: on current firmwares /device and
    /wan/ip/stats answer 200 without authentication, so they cannot detect a
    wrong password. /hosts answers 401 without a valid login.

    Returns the form errors and, when the box answered, its device info:
    the serial number is used as the config entry unique ID.
    """
    session = async_create_clientsession(
        hass, verify_ssl=verify_ssl, cookie_jar=CookieJar(unsafe=True)
    )
    client = BboxClient(
        password, host, use_tls=True, verify_ssl=verify_ssl, session=session
    )
    errors: dict[str, str] = {}
    device: DeviceInfo | None = None
    try:
        await client.get_hosts()
        device = await client.get_device()
    except BboxAuthenticationError:
        errors["base"] = "invalid_auth"
    except BboxConnectionError, BboxTimeoutError:
        errors["base"] = "cannot_connect"
    except BboxRateLimitError:
        # The box blocks authentication after too many attempts (HTTP 429):
        # tell the user to wait instead of hammering the login endpoint.
        errors["base"] = "rate_limited"
    except BboxApiError:
        errors["base"] = "unknown"
    return errors, device


class BboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bbox."""

    VERSION = 1

    def _async_entry_for_host(self, host: str) -> ConfigEntry | None:
        """Return the current entry configured for a host, if any."""
        return next(
            (
                entry
                for entry in self._async_current_entries()
                if entry.data[CONF_HOST] == host
            ),
            None,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].rstrip("/")
            errors, device = await _async_validate(
                self.hass,
                host,
                user_input[CONF_PASSWORD],
                user_input[CONF_VERIFY_SSL],
            )
            if not errors and device is not None and not device.serialnumber:
                # Without a serial number no stable unique ID is available.
                errors["base"] = "unknown"
            if not errors and device is not None and device.serialnumber:
                # The serial number is stable when the box gets a new IP
                # address, unlike the host.
                await self.async_set_unique_id(device.serialnumber)
                self._abort_if_unique_id_configured()
                if self._async_entry_for_host(host) is not None:
                    # An entry imported from YAML (host-based unique ID)
                    # already covers this box.
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=host, data={**user_input, CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle the import of a legacy YAML platform configuration.

        The sensor and the device_tracker platforms of one box import into
        the same entry: merge into the existing entry matched by host when
        the other platform was imported first or the box was set up through
        the UI (unique id = serial number).
        """
        host = import_data[CONF_HOST].rstrip("/")
        # Imported YAML entries carry no password, so the serial number
        # cannot be fetched here; the host is the only identifier available.
        # pylint: disable-next=home-assistant-unique-id-ip-based
        await self.async_set_unique_id(host)
        entry_data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_PASSWORD: import_data[CONF_PASSWORD],
            CONF_VERIFY_SSL: import_data[CONF_VERIFY_SSL],
        }
        if CONF_MONITORED_VARIABLES in import_data:
            entry_data[CONF_NAME] = import_data.get(CONF_NAME, DEFAULT_NAME)
            entry_data[CONF_MONITORED_VARIABLES] = list(
                import_data[CONF_MONITORED_VARIABLES]
            )
        for entry in self._async_current_entries():
            # Match both imported entries (unique ID = host) and entries
            # created through the UI or a reconfiguration (unique ID =
            # serial number): one box must stay one entry.
            if host in (entry.unique_id, entry.data[CONF_HOST]):
                merged_data = {**entry.data, **entry_data}
                if entry.data[CONF_PASSWORD]:
                    # The platform schemas insert password="" when it is
                    # omitted: keep the password saved on the entry (user
                    # flow or reauthentication).
                    merged_data[CONF_PASSWORD] = entry.data[CONF_PASSWORD]
                # Same for verify_ssl: the schema default True must not
                # override a saved False.
                merged_data[CONF_VERIFY_SSL] = entry.data[CONF_VERIFY_SSL]
                self.hass.config_entries.async_update_entry(entry, data=merged_data)
                if entry.state is ConfigEntryState.LOADED:
                    # The newly imported platform is only forwarded on reload.
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")
        return self.async_create_entry(title=host, data=entry_data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration, e.g. the box moved to a new IP address."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].rstrip("/")
            errors, device = await _async_validate(
                self.hass,
                host,
                user_input[CONF_PASSWORD],
                user_input[CONF_VERIFY_SSL],
            )
            if not errors and device is not None and not device.serialnumber:
                # Without a serial number no stable unique ID is available.
                errors["base"] = "unknown"
            if not errors and device is not None and device.serialnumber:
                # The serial number is stable when the box gets a new IP
                # address, unlike the host.
                await self.async_set_unique_id(device.serialnumber)
                if (
                    existing
                    := self.hass.config_entries.async_entry_for_domain_unique_id(
                        DOMAIN, device.serialnumber
                    )
                ) is not None and existing.entry_id != reconfigure_entry.entry_id:
                    # The new host points to a box already configured on
                    # another entry.
                    return self.async_abort(reason="already_configured")
                # The target host must not be configured on another entry
                # (e.g. a YAML import with a host-based unique ID).
                self._async_abort_entries_match({CONF_HOST: host})
                if (
                    reconfigure_entry.unique_id is not None
                    and reconfigure_entry.unique_id != reconfigure_entry.data[CONF_HOST]
                    and reconfigure_entry.unique_id != device.serialnumber
                ):
                    # The entry already has a serial-based identity: pointing
                    # it at another box would re-attribute its entities and
                    # history to a different router. Host-based YAML entries
                    # migrate to the serial number instead.
                    return self.async_abort(reason="different_device")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    unique_id=device.serialnumber,
                    title=host,
                    data_updates={
                        CONF_HOST: host,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or reconfigure_entry.data),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication: imported YAML configurations have no password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the admin password and validate it against the box."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors, device = await _async_validate(
                self.hass,
                reauth_entry.data[CONF_HOST],
                user_input[CONF_PASSWORD],
                user_input[CONF_VERIFY_SSL],
            )
            if not errors:
                data_updates = {
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
                if device is not None and device.serialnumber:
                    serial = device.serialnumber
                    if (
                        other_entry
                        := self.hass.config_entries.async_entry_for_domain_unique_id(
                            DOMAIN, serial
                        )
                    ) is not None and other_entry.entry_id != reauth_entry.entry_id:
                        # Another entry already identifies this box.
                        return self.async_abort(reason="already_configured")
                    if (
                        reauth_entry.unique_id is not None
                        and reauth_entry.unique_id != reauth_entry.data[CONF_HOST]
                        and reauth_entry.unique_id != serial
                    ):
                        # A serial-based entry must stay the same box.
                        return self.async_abort(reason="different_device")
                    # Host-based YAML entries adopt the stable serial identity.
                    return self.async_update_reload_and_abort(
                        reauth_entry, unique_id=serial, data_updates=data_updates
                    )
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=data_updates
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(reauth_entry.data),
            errors=errors,
        )
