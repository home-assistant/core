"""The enphase_envoy component."""

from __future__ import annotations

import contextlib
import datetime
from datetime import timedelta
import logging
from typing import Any

from pyenphase import Envoy, EnvoyError, EnvoyTokenAuth
from pyenphase.models.home import EnvoyInterfaceInformation

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, INVALID_AUTH_ERRORS

SCAN_INTERVAL = timedelta(seconds=60)

TOKEN_REFRESH_CHECK_INTERVAL = timedelta(days=1)
STALE_TOKEN_THRESHOLD = timedelta(days=30).total_seconds()
NOTIFICATION_ID = "enphase_envoy_notification"
FIRMWARE_REFRESH_INTERVAL = timedelta(hours=4)
MAC_VERIFICATION_DELAY = timedelta(seconds=34)
_LOGGER = logging.getLogger(__name__)


type EnphaseConfigEntry = ConfigEntry[EnphaseUpdateCoordinator]


class EnphaseUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator to gather data from any envoy."""

    envoy_serial_number: str
    envoy_firmware: str
    config_entry: EnphaseConfigEntry
    interface: EnvoyInterfaceInformation | None

    def __init__(
        self, hass: HomeAssistant, envoy: Envoy, entry: EnphaseConfigEntry
    ) -> None:
        """Initialize DataUpdateCoordinator for the envoy."""
        self.envoy = envoy
        entry_data = entry.data
        self.username = entry_data[CONF_USERNAME]
        self.password = entry_data[CONF_PASSWORD]
        self._setup_complete = False
        self.envoy_firmware = ""
        self.interface = None
        self._cancel_token_refresh: CALLBACK_TYPE | None = None
        self._cancel_firmware_refresh: CALLBACK_TYPE | None = None
        self._cancel_mac_verification: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry_data[CONF_NAME],
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )

    @callback
    def _async_refresh_token_if_needed(self, now: datetime.datetime) -> None:
        """Proactively refresh token if its stale in case cloud services goes down."""
        assert isinstance(self.envoy.auth, EnvoyTokenAuth)
        expire_time = self.envoy.auth.expire_timestamp
        remain = expire_time - now.timestamp()
        fresh = remain > STALE_TOKEN_THRESHOLD
        name = self.name
        _LOGGER.debug("%s: %s seconds remaining on token fresh=%s", name, remain, fresh)
        if not fresh:
            self.hass.async_create_background_task(
                self._async_try_refresh_token(), "{name} token refresh"
            )

    async def _async_try_refresh_token(self) -> None:
        """Try to refresh token."""
        assert isinstance(self.envoy.auth, EnvoyTokenAuth)
        _LOGGER.debug("%s: Trying to refresh token", self.name)
        try:
            await self.envoy.auth.refresh()
        except EnvoyError as err:
            # If we can't refresh the token, we try again later
            # If the token actually ends up expiring, we'll
            # re-authenticate with username/password and get a new token
            # or log an error if that fails
            _LOGGER.debug("%s: Error refreshing token: %s", err, self.name)
            return
        self._async_update_saved_token()

    @callback
    def _async_refresh_firmware(self, now: datetime.datetime) -> None:
        """Proactively check for firmware changes in Envoy."""
        self.hass.async_create_background_task(
            self._async_try_refresh_firmware(), "{name} firmware refresh"
        )

    async def _async_try_refresh_firmware(self) -> None:
        """Check firmware in Envoy and reload config entry if changed."""
        # envoy.setup just reads firmware, serial and partnumber from /info
        try:
            await self.envoy.setup()
        except EnvoyError as err:
            # just try again next time
            _LOGGER.debug("%s: Error reading firmware: %s", err, self.name)
            return
        if (current_firmware := self.envoy_firmware) and current_firmware != (
            new_firmware := self.envoy.firmware
        ):
            self.envoy_firmware = new_firmware
            _LOGGER.warning(
                "Envoy firmware changed from: %s to: %s, reloading config entry %s",
                current_firmware,
                new_firmware,
                self.name,
            )
            # reload the integration to get all established again
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )

    def _schedule_mac_verification(
        self, delay: timedelta = MAC_VERIFICATION_DELAY
    ) -> None:
        """Schedule one time job to verify envoy mac address."""
        self.async_cancel_mac_verification()
        self._cancel_mac_verification = async_call_later(
            self.hass,
            delay,
            self._async_verify_mac,
        )

    @callback
    def _async_verify_mac(self, now: datetime.datetime) -> None:
        """Verify Envoy active interface mac address in background."""
        self.hass.async_create_background_task(
            self._async_fetch_and_compare_mac(), "{name} verify envoy mac address"
        )

    async def _async_fetch_and_compare_mac(self) -> None:
        """Get Envoy interface information and update mac in device connections."""
        interface: (
            EnvoyInterfaceInformation | None
        ) = await self.envoy.interface_settings()
        if interface is None:
            _LOGGER.debug("%s: interface information returned None", self.name)
            return
        # remember interface information so diagnostics can include in report
        self.interface = interface

        # Add to or update device registry connections as needed
        device_registry = dr.async_get(self.hass)
        envoy_device = device_registry.async_get_device(
            identifiers={
                (
                    DOMAIN,
                    self.envoy_serial_number,
                )
            }
        )
        if envoy_device is None:
            _LOGGER.error(
                "No envoy device found in device registry: %s %s",
                DOMAIN,
                self.envoy_serial_number,
            )
            return

        connection = (dr.CONNECTION_NETWORK_MAC, interface.mac)
        if connection in envoy_device.connections:
            _LOGGER.debug(
                "connection verified as existing: %s in %s", connection, self.name
            )
            return

        device_registry.async_update_device(
            device_id=envoy_device.id,
            new_connections={connection},
        )
        _LOGGER.debug("added connection: %s to %s", connection, self.name)

    @callback
    def _async_mark_setup_complete(self) -> None:
        """Mark setup as complete and setup firmware checks and token refresh if needed."""
        self._setup_complete = True
        self.async_cancel_firmware_refresh()
        self._cancel_firmware_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_firmware,
            FIRMWARE_REFRESH_INTERVAL,
            cancel_on_shutdown=True,
        )
        self._schedule_mac_verification()
        self.async_cancel_token_refresh()
        if not isinstance(self.envoy.auth, EnvoyTokenAuth):
            return
        self._cancel_token_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_token_if_needed,
            TOKEN_REFRESH_CHECK_INTERVAL,
            cancel_on_shutdown=True,
        )

    async def _async_setup_and_authenticate(self) -> None:
        """Set up and authenticate with the envoy."""
        envoy = self.envoy
        await envoy.setup()
        assert envoy.serial_number is not None
        self.envoy_serial_number = envoy.serial_number
        if token := self.config_entry.data.get(CONF_TOKEN):
            with contextlib.suppress(*INVALID_AUTH_ERRORS):
                # Always set the username and password
                # so we can refresh the token if needed
                await envoy.authenticate(
                    username=self.username, password=self.password, token=token
                )
                # The token is valid, but we still want
                # to refresh it if it's stale right away
                self._async_refresh_token_if_needed(dt_util.utcnow())
                return
            # token likely expired or firmware changed
            # so we fall through to authenticate with
            # username/password
        await self.envoy.authenticate(username=self.username, password=self.password)
        # Password auth succeeded, so we can update the token
        # if we are using EnvoyTokenAuth
        self._async_update_saved_token()

    def _async_update_saved_token(self) -> None:
        """Update saved token in config entry."""
        envoy = self.envoy
        if not isinstance(envoy.auth, EnvoyTokenAuth):
            return
        # update token in config entry so we can
        # startup without hitting the Cloud API
        # as long as the token is valid
        _LOGGER.debug("%s: Updating token in config entry from auth", self.name)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_TOKEN: envoy.auth.token,
            },
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all device and sensor data from api."""
        envoy = self.envoy
        for tries in range(2):
            try:
                if not self._setup_complete:
                    await self._async_setup_and_authenticate()
                    self._async_mark_setup_complete()
                # dump all received data in debug mode to assist troubleshooting
                envoy_data = await envoy.update()
            except INVALID_AUTH_ERRORS as err:
                if self._setup_complete and tries == 0:
                    # token likely expired or firmware changed, try to re-authenticate
                    self._setup_complete = False
                    continue
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_error",
                    translation_placeholders={
                        "host": envoy.host,
                        "args": err.args[0],
                    },
                ) from err
            except EnvoyError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="envoy_error",
                    translation_placeholders={
                        "host": envoy.host,
                        "args": err.args[0],
                    },
                ) from err

            # if we have a firmware version from previous setup, compare to current one
            # when envoy gets new firmware there will be an authentication failure
            # which results in getting fw version again, if so reload the integration.
            if (current_firmware := self.envoy_firmware) and current_firmware != (
                new_firmware := envoy.firmware
            ):
                _LOGGER.warning(
                    "Envoy firmware changed from: %s to: %s, reloading enphase envoy integration",
                    current_firmware,
                    new_firmware,
                )
                # reload the integration to get all established again
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )
            # remember firmware version for next time
            self.envoy_firmware = envoy.firmware
            _LOGGER.debug("Envoy data: %s", envoy_data)
            return envoy_data.raw

        raise RuntimeError("Unreachable code in _async_update_data")  # pragma: no cover

    @callback
    def async_cancel_token_refresh(self) -> None:
        """Cancel token refresh."""
        if self._cancel_token_refresh:
            self._cancel_token_refresh()
            self._cancel_token_refresh = None

    @callback
    def async_cancel_firmware_refresh(self) -> None:
        """Cancel firmware refresh."""
        if self._cancel_firmware_refresh:
            self._cancel_firmware_refresh()
            self._cancel_firmware_refresh = None

    @callback
    def async_cancel_mac_verification(self) -> None:
        """Cancel mac verification."""
        if self._cancel_mac_verification:
            self._cancel_mac_verification()
            self._cancel_mac_verification = None
