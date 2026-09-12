"""DataUpdateCoordinator for the Cookidoo integration."""

from collections.abc import Callable, Coroutine
from dataclasses import asdict, dataclass
from datetime import timedelta
from functools import wraps
import logging
from typing import Any, Concatenate, Protocol, override

from cookidoo_api import (
    Cookidoo,
    CookidooAdditionalItem,
    CookidooAuthException,
    CookidooException,
    CookidooIngredientItem,
    CookidooRequestException,
    CookidooSubscription,
    CookidooUserInfo,
)
from cookidoo_api.types import CookidooCalendarDay

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type CookidooConfigEntry = ConfigEntry[CookidooDataUpdateCoordinator]


class _AuthDataHolder(Protocol):
    """Something able to persist the tokens, i.e. the coordinator or an entity."""

    def save_auth_data(self) -> None: ...


def persist_auth_data[T: _AuthDataHolder, **P, R](
    func: Callable[Concatenate[T, P], Coroutine[Any, Any, R]],
) -> Callable[Concatenate[T, P], Coroutine[Any, Any, R]]:
    """Persist the tokens the library may rotate while the wrapped call runs.

    Any request can transparently refresh the access token and hand back a new
    refresh token, so the result has to be stored whether the call succeeded or
    raised, or a restart can restore a refresh token the server already retired.
    """

    @wraps(func)
    async def wrapper(self: T, *args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(self, *args, **kwargs)
        finally:
            self.save_auth_data()

    return wrapper


@dataclass
class CookidooData:
    """Cookidoo data type."""

    ingredient_items: list[CookidooIngredientItem]
    additional_items: list[CookidooAdditionalItem]
    subscription: CookidooSubscription | None
    week_plan: list[CookidooCalendarDay]


class CookidooDataUpdateCoordinator(DataUpdateCoordinator[CookidooData]):
    """A Cookidoo Data Update Coordinator."""

    config_entry: CookidooConfigEntry
    user: CookidooUserInfo

    def __init__(
        self, hass: HomeAssistant, cookidoo: Cookidoo, entry: CookidooConfigEntry
    ) -> None:
        """Initialize the Cookidoo data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=90),
            config_entry=entry,
        )
        self.cookidoo = cookidoo

    async def _async_login(self) -> CookidooUserInfo:
        """Return the user info, reusing the persisted tokens while they are valid."""
        if self.cookidoo.auth_data is not None:
            try:
                return await self.cookidoo.get_user_info()
            except CookidooAuthException:
                _LOGGER.debug("Stored tokens are no longer valid, logging in again")
        await self.cookidoo.login()
        return await self.cookidoo.get_user_info()

    def save_auth_data(self) -> None:
        """Persist the OAuth2 tokens so a restart does not need a new login."""
        if (auth_data := self.cookidoo.auth_data) is None:
            return
        token = asdict(auth_data)
        if self.config_entry.data.get(CONF_TOKEN) == token:
            return
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_TOKEN: token},
        )

    @override
    @persist_auth_data
    async def _async_setup(self) -> None:
        try:
            self.user = await self._async_login()
        except CookidooRequestException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_request_exception",
            ) from e
        except CookidooAuthException as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="setup_authentication_exception",
                translation_placeholders={
                    CONF_EMAIL: self.config_entry.data[CONF_EMAIL]
                },
            ) from e
        except CookidooException as e:
            # login() scrapes the CIAM login page, so it can also fail to parse it
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_request_exception",
            ) from e

    @override
    @persist_auth_data
    async def _async_update_data(self) -> CookidooData:
        try:
            ingredient_items = await self.cookidoo.get_ingredient_items()
            additional_items = await self.cookidoo.get_additional_items()
            subscription = await self.cookidoo.get_active_subscription()
            week_plan = await self.cookidoo.get_recipes_in_calendar_week(
                dt_util.now().date()
            )
        except CookidooAuthException:
            try:
                await self.cookidoo.login()
            except CookidooAuthException as exc:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={
                        CONF_EMAIL: self.config_entry.data[CONF_EMAIL]
                    },
                ) from exc
            except CookidooException as exc:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_request_exception",
                ) from exc
            _LOGGER.debug(
                "Authentication failed but re-authentication"
                " was successful, trying again later"
            )
            return self.data
        except CookidooException as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_exception",
            ) from e

        return CookidooData(
            ingredient_items=ingredient_items,
            additional_items=additional_items,
            subscription=subscription,
            week_plan=week_plan,
        )
