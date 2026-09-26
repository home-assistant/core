"""Config flow for Mitsubishi Comfort integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from mitsubishi_comfort import MitsubishiCloudAccount
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import probatio

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_ADDRESSES, CONF_CREDENTIALS, DOMAIN
from .helpers import build_credentials, is_fully_credentialed

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


class MitsubishiComfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Mitsubishi Comfort."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        # Fields recovered by earlier attempts in this flow, replayed on retry:
        # the rate-limited Socket.IO password fetch may succeed on one attempt
        # and return nothing on the next, so no single attempt has to recover
        # everything.
        self._cached_credentials: dict[str, dict[str, str]] = {}
        self._cached_username: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # The recovered fields belong to the account entered.
            if user_input[CONF_USERNAME] != self._cached_username:
                self._cached_username = user_input[CONF_USERNAME]
                self._cached_credentials = {}

            account = MitsubishiCloudAccount(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )

            devices: dict = {}
            try:
                await account.login()
                devices = await account.discover_devices(
                    cached_credentials=self._cached_credentials, cloud_fallback=True
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except DeviceConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error discovering Mitsubishi Comfort devices"
                )
                errors["base"] = "unknown"
            else:
                _LOGGER.debug("Discovered %d device(s)", len(devices))

            if not errors:
                await self.async_set_unique_id(account.user_id)
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    entry = self._get_reauth_entry()
                    credentials = dict(entry.data.get(CONF_CREDENTIALS, {}))
                    # A throttled discovery on reload may not return these fields again.
                    for serial, recovered in build_credentials(devices).items():
                        cached = credentials.get(serial, {})
                        credentials[serial] = {
                            key: value or cached.get(key, "")
                            for key, value in recovered.items()
                        }
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={**user_input, CONF_CREDENTIALS: credentials},
                    )
                self._abort_if_unique_id_configured()

                # Persist the fields discovered here for async_setup_entry to
                # replay via discover_devices(cached_credentials=...): the
                # slow, rate-limited Socket.IO call then runs only for
                # passwords still missing.
                credentials = build_credentials(devices)
                if credentials:
                    self._cached_credentials = credentials
                if not devices:
                    errors["base"] = "no_devices"
                elif not any(
                    info.is_indoor_unit or is_fully_credentialed(info)
                    for info in devices.values()
                ):
                    errors["base"] = "no_usable_devices"
                else:
                    return self.async_create_entry(
                        title=f"Mitsubishi Comfort ({user_input[CONF_USERNAME]})",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_CREDENTIALS: credentials,
                        },
                    )

        return self.async_show_form(
            step_id="reauth_confirm" if self.source == SOURCE_REAUTH else "user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauthenticate without replacing cached local credentials."""
        self._cached_username = entry_data[CONF_USERNAME]
        self._cached_credentials = entry_data.get(CONF_CREDENTIALS, {})
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the credentials for the existing account."""
        return await self.async_step_user(user_input)

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a registered device discovered on the local network via DHCP.

        The cloud API never returns a device's LAN IP, so DHCP discovery is the
        source of addresses. Each device is registered with its MAC during setup,
        so "registered_devices" discovery only fires for our own devices: record
        the IP on the owning entry and reload to set the device up or recover a
        changed IP.
        """
        mac = dr.format_mac(discovery_info.macaddress)
        devices = dr.async_get(self.hass).async_get_devices(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)}
        )
        device_entry_ids = {device.config_entry_id for device in devices}
        entry = next(
            (
                entry
                for entry in self._async_current_entries(include_ignore=False)
                if entry.entry_id in device_entry_ids
            ),
            None,
        )
        if entry is None:
            return self.async_abort(reason="already_configured")

        addresses = entry.data.get(CONF_ADDRESSES, {})
        if addresses.get(mac) != discovery_info.ip:
            _LOGGER.debug("DHCP discovery resolved %s to %s", mac, discovery_info.ip)
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_ADDRESSES: {**addresses, mac: discovery_info.ip},
                },
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason="already_configured")
