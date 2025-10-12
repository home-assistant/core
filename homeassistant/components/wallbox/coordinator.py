"""DataUpdateCoordinator for the wallbox integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Any, Concatenate

import requests
from wallbox import Wallbox

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHARGER_CURRENCY_KEY,
    CHARGER_DATA_KEY,
    CHARGER_DATA_POST_L1_KEY,
    CHARGER_DATA_POST_L2_KEY,
    CHARGER_ECO_SMART_KEY,
    CHARGER_ECO_SMART_MODE_KEY,
    CHARGER_ECO_SMART_STATUS_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_FEATURES_KEY,
    CHARGER_JWT_REFRESH_TOKEN,
    CHARGER_JWT_REFRESH_TTL,
    CHARGER_JWT_TOKEN,
    CHARGER_JWT_TTL,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_MAX_CHARGING_CURRENT_POST_KEY,
    CHARGER_MAX_ICP_CURRENT_KEY,
    CHARGER_PLAN_KEY,
    CHARGER_POWER_BOOST_KEY,
    CHARGER_STATUS_DESCRIPTION_KEY,
    CHARGER_STATUS_ID_KEY,
    CODE_KEY,
    CONF_STATION,
    DOMAIN,
    UPDATE_INTERVAL,
    ChargerStatus,
    EcoSmartMode,
)

_LOGGER = logging.getLogger(__name__)

# Translation of StatusId based on Wallbox portal code:
# https://my.wallbox.com/src/utilities/charger/chargerStatuses.js
CHARGER_STATUS: dict[int, ChargerStatus] = {
    0: ChargerStatus.DISCONNECTED,
    14: ChargerStatus.ERROR,
    15: ChargerStatus.ERROR,
    161: ChargerStatus.READY,
    162: ChargerStatus.READY,
    163: ChargerStatus.DISCONNECTED,
    164: ChargerStatus.WAITING,
    165: ChargerStatus.LOCKED,
    166: ChargerStatus.UPDATING,
    177: ChargerStatus.SCHEDULED,
    178: ChargerStatus.PAUSED,
    179: ChargerStatus.SCHEDULED,
    180: ChargerStatus.WAITING_FOR_CAR,
    181: ChargerStatus.WAITING_FOR_CAR,
    182: ChargerStatus.PAUSED,
    183: ChargerStatus.WAITING_IN_QUEUE_POWER_SHARING,
    184: ChargerStatus.WAITING_IN_QUEUE_POWER_SHARING,
    185: ChargerStatus.WAITING_IN_QUEUE_POWER_BOOST,
    186: ChargerStatus.WAITING_IN_QUEUE_POWER_BOOST,
    187: ChargerStatus.WAITING_MID_FAILED,
    188: ChargerStatus.WAITING_MID_SAFETY,
    189: ChargerStatus.WAITING_IN_QUEUE_ECO_SMART,
    193: ChargerStatus.CHARGING,
    194: ChargerStatus.CHARGING,
    195: ChargerStatus.CHARGING,
    196: ChargerStatus.DISCHARGING,
    209: ChargerStatus.LOCKED,
    210: ChargerStatus.LOCKED_CAR_CONNECTED,
}

type WallboxConfigEntry = ConfigEntry[WallboxCoordinator]


def _require_authentication[_WallboxCoordinatorT: WallboxCoordinator, **_P](
    func: Callable[Concatenate[_WallboxCoordinatorT, _P], Any],
) -> Callable[Concatenate[_WallboxCoordinatorT, _P], Any]:
    """Authenticate with decorator using Wallbox API."""

    async def require_authentication(
        self: _WallboxCoordinatorT, *args: _P.args, **kwargs: _P.kwargs
    ) -> Any:
        """Authenticate using Wallbox API."""
        await self.async_authenticate()
        return await func(self, *args, **kwargs)

    return require_authentication


def check_token_validity(jwtTokenTTL: int, jwtTokenDrift: int) -> bool:
    """Check if the jwtToken is still valid in order to reuse if possible."""
    return round((jwtTokenTTL / 1000) - jwtTokenDrift, 0) > datetime.timestamp(
        datetime.now()
    )


def _validate(wallbox: Wallbox) -> None:
    """Authenticate using Wallbox API to check if the used credentials are valid."""
    try:
        wallbox.authenticate()
    except requests.exceptions.HTTPError as wallbox_connection_error:
        if wallbox_connection_error.response.status_code == 403:
            raise InvalidAuth(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from wallbox_connection_error
        raise ConnectionError from wallbox_connection_error


async def async_validate_input(hass: HomeAssistant, wallbox: Wallbox) -> None:
    """Get new sensor data for Wallbox component."""
    await hass.async_add_executor_job(_validate, wallbox)


class WallboxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Wallbox Coordinator class."""

    config_entry: WallboxConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: WallboxConfigEntry, wallbox: Wallbox
    ) -> None:
        """Initialize."""
        self._station = config_entry.data[CONF_STATION]
        self._wallbox = wallbox

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def _authenticate(self) -> dict[str, str]:
        """Authenticate using Wallbox API. First check token validity."""
        options = dict(self.config_entry.options)
        if not check_token_validity(
            jwtTokenTTL=options.get(CHARGER_JWT_TTL, 0),
            jwtTokenDrift=UPDATE_INTERVAL,
        ):
            try:
                self._wallbox.authenticate()
                options[CHARGER_JWT_TOKEN] = self._wallbox.jwtToken
                options[CHARGER_JWT_REFRESH_TOKEN] = self._wallbox.jwtRefreshToken
                options[CHARGER_JWT_TTL] = self._wallbox.jwtTokenTtl
                options[CHARGER_JWT_REFRESH_TTL] = self._wallbox.jwtRefreshTokenTtl
            except requests.exceptions.HTTPError as wallbox_connection_error:
                if (
                    wallbox_connection_error.response.status_code
                    == HTTPStatus.FORBIDDEN
                ):
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN, translation_key="invalid_auth"
                    ) from wallbox_connection_error
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="api_failed"
                ) from wallbox_connection_error
        return options

    async def async_authenticate(self) -> None:
        """Authenticate using Wallbox API."""
        options = await self.hass.async_add_executor_job(self._authenticate)
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    def _get_data(self) -> dict[str, Any]:
        """Get new sensor data for Wallbox component."""
        try:
            data: dict[str, Any] = self._wallbox.getChargerStatus(self._station)
            data[CHARGER_MAX_CHARGING_CURRENT_KEY] = data[CHARGER_DATA_KEY][
                CHARGER_MAX_CHARGING_CURRENT_KEY
            ]
            data[CHARGER_LOCKED_UNLOCKED_KEY] = data[CHARGER_DATA_KEY][
                CHARGER_LOCKED_UNLOCKED_KEY
            ]
            data[CHARGER_ENERGY_PRICE_KEY] = data[CHARGER_DATA_KEY][
                CHARGER_ENERGY_PRICE_KEY
            ]
            # Only show max_icp_current if power_boost is available in the wallbox unit:
            if (
                data[CHARGER_DATA_KEY].get(CHARGER_MAX_ICP_CURRENT_KEY, 0) > 0
                and CHARGER_POWER_BOOST_KEY
                in data[CHARGER_DATA_KEY][CHARGER_PLAN_KEY][CHARGER_FEATURES_KEY]
            ):
                data[CHARGER_MAX_ICP_CURRENT_KEY] = data[CHARGER_DATA_KEY][
                    CHARGER_MAX_ICP_CURRENT_KEY
                ]

            data[CHARGER_CURRENCY_KEY] = (
                f"{data[CHARGER_DATA_KEY][CHARGER_CURRENCY_KEY][CODE_KEY]}/kWh"
            )

            data[CHARGER_STATUS_DESCRIPTION_KEY] = CHARGER_STATUS.get(
                data[CHARGER_STATUS_ID_KEY], ChargerStatus.UNKNOWN
            )

            # Set current solar charging mode
            eco_smart_enabled = (
                data[CHARGER_DATA_KEY]
                .get(CHARGER_ECO_SMART_KEY, {})
                .get(CHARGER_ECO_SMART_STATUS_KEY)
            )

            eco_smart_mode = (
                data[CHARGER_DATA_KEY]
                .get(CHARGER_ECO_SMART_KEY, {})
                .get(CHARGER_ECO_SMART_MODE_KEY)
            )
            if eco_smart_mode is None:
                data[CHARGER_ECO_SMART_KEY] = EcoSmartMode.DISABLED
            elif eco_smart_enabled is False:
                data[CHARGER_ECO_SMART_KEY] = EcoSmartMode.OFF
            elif eco_smart_mode == 0:
                data[CHARGER_ECO_SMART_KEY] = EcoSmartMode.ECO_MODE
            elif eco_smart_mode == 1:
                data[CHARGER_ECO_SMART_KEY] = EcoSmartMode.FULL_SOLAR
            return data  # noqa: TRY300
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 429:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="too_many_requests"
                ) from wallbox_connection_error
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="api_failed"
            ) from wallbox_connection_error

    @_require_authentication
    async def _async_update_data(self) -> dict[str, Any]:
        """Get new sensor data for Wallbox component. Set update interval to be UPDATE_INTERVAL * #wallbox chargers configured, this is necessary due to rate limitations."""

        self.update_interval = timedelta(
            seconds=UPDATE_INTERVAL
            * max(len(self.hass.config_entries.async_loaded_entries(DOMAIN)), 1)
        )
        return await self.hass.async_add_executor_job(self._get_data)

    def _set_charging_current(
        self, charging_current: float
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Set maximum charging current for Wallbox."""
        try:
            result = self._wallbox.setMaxChargingCurrent(
                self._station, charging_current
            )
            data = self.data
            data[CHARGER_MAX_CHARGING_CURRENT_KEY] = result[CHARGER_DATA_POST_L1_KEY][
                CHARGER_DATA_POST_L2_KEY
            ][CHARGER_MAX_CHARGING_CURRENT_POST_KEY]
            return data  # noqa: TRY300
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InsufficientRights(
                    translation_domain=DOMAIN,
                    translation_key="insufficient_rights",
                    hass=self.hass,
                ) from wallbox_connection_error
            if wallbox_connection_error.response.status_code == 429:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="too_many_requests"
                ) from wallbox_connection_error
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_failed"
            ) from wallbox_connection_error

    @_require_authentication
    async def async_set_charging_current(self, charging_current: float) -> None:
        """Set maximum charging current for Wallbox."""
        data = await self.hass.async_add_executor_job(
            self._set_charging_current, charging_current
        )
        self.async_set_updated_data(data)

    def _set_icp_current(self, icp_current: float) -> dict[str, Any]:
        """Set maximum icp current for Wallbox."""
        try:
            result = self._wallbox.setIcpMaxCurrent(self._station, icp_current)
            data = self.data
            data[CHARGER_MAX_ICP_CURRENT_KEY] = result[CHARGER_MAX_ICP_CURRENT_KEY]
            return data  # noqa: TRY300
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InsufficientRights(
                    translation_domain=DOMAIN,
                    translation_key="insufficient_rights",
                    hass=self.hass,
                ) from wallbox_connection_error
            if wallbox_connection_error.response.status_code == 429:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="too_many_requests"
                ) from wallbox_connection_error
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_failed"
            ) from wallbox_connection_error

    @_require_authentication
    async def async_set_icp_current(self, icp_current: float) -> None:
        """Set maximum icp current for Wallbox."""
        data = await self.hass.async_add_executor_job(
            self._set_icp_current, icp_current
        )
        self.async_set_updated_data(data)

    def _set_energy_cost(self, energy_cost: float) -> dict[str, Any]:
        """Set energy cost for Wallbox."""
        try:
            result = self._wallbox.setEnergyCost(self._station, energy_cost)
            data = self.data
            data[CHARGER_ENERGY_PRICE_KEY] = result[CHARGER_ENERGY_PRICE_KEY]
            return data  # noqa: TRY300
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 429:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="too_many_requests"
                ) from wallbox_connection_error
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_failed"
            ) from wallbox_connection_error

    @_require_authentication
    async def async_set_energy_cost(self, energy_cost: float) -> None:
        """Set energy cost for Wallbox."""
        data = await self.hass.async_add_executor_job(
            self._set_energy_cost, energy_cost
        )
        self.async_set_updated_data(data)

    def _set_lock_unlock(self, lock: bool) -> dict[str, dict[str, dict[str, Any]]]:
        """Set wallbox to locked or unlocked."""
        try:
            if lock:
                result = self._wallbox.lockCharger(self._station)
            else:
                result = self._wallbox.unlockCharger(self._station)
            data = self.data
            data[CHARGER_LOCKED_UNLOCKED_KEY] = result[CHARGER_DATA_POST_L1_KEY][
                CHARGER_DATA_POST_L2_KEY
            ][CHARGER_LOCKED_UNLOCKED_KEY]
            return data  # noqa: TRY300
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InsufficientRights(
                    translation_domain=DOMAIN,
                    translation_key="insufficient_rights",
                    hass=self.hass,
                ) from wallbox_connection_error
            if wallbox_connection_error.response.status_code == 429:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="too_many_requests"
                ) from wallbox_connection_error
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_failed"
            ) from wallbox_connection_error

    @_require_authentication
    async def async_set_lock_unlock(self, lock: bool) -> None:
        """Set wallbox to locked or unlocked."""
        data = await self.hass.async_add_executor_job(self._set_lock_unlock, lock)
        self.async_set_updated_data(data)

    def _pause_charger(self, pause: bool) -> None:
        """Set wallbox to pause or resume."""
        try:
            if pause:
                self._wallbox.pauseChargingSession(self._station)
            else:
                self._wallbox.resumeChargingSession(self._station)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 429:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="too_many_requests"
                ) from wallbox_connection_error
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_failed"
            ) from wallbox_connection_error

    @_require_authentication
    async def async_pause_charger(self, pause: bool) -> None:
        """Set wallbox to pause or resume."""
        await self.hass.async_add_executor_job(self._pause_charger, pause)
        await self.async_request_refresh()

    def _set_eco_smart(self, option: str) -> None:
        """Set wallbox solar charging mode."""
        try:
            if option == EcoSmartMode.ECO_MODE:
                self._wallbox.enableEcoSmart(self._station, 0)
            elif option == EcoSmartMode.FULL_SOLAR:
                self._wallbox.enableEcoSmart(self._station, 1)
            else:
                self._wallbox.disableEcoSmart(self._station)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 429:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="too_many_requests"
                ) from wallbox_connection_error
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_failed"
            ) from wallbox_connection_error

    @_require_authentication
    async def async_set_eco_smart(self, option: str) -> None:
        """Set wallbox solar charging mode."""

        await self.hass.async_add_executor_job(self._set_eco_smart, option)
        await self.async_request_refresh()


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InsufficientRights(HomeAssistantError):
    """Error to indicate there are insufficient right for the user."""

    def __init__(
        self,
        *args: object,
        translation_domain: str | None = None,
        translation_key: str | None = None,
        translation_placeholders: dict[str, str] | None = None,
        hass: HomeAssistant,
    ) -> None:
        """Initialize exception."""
        super().__init__(
            self, *args, translation_domain, translation_key, translation_placeholders
        )
        self.hass = hass
        self._create_insufficient_rights_issue()

    def _create_insufficient_rights_issue(self) -> None:
        """Creates an issue for insufficient rights."""
        ir.create_issue(
            self.hass,
            DOMAIN,
            "insufficient_rights",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            learn_more_url="https://www.home-assistant.io/integrations/wallbox/#troubleshooting",
            translation_key="insufficient_rights",
        )
