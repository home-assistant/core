"""Support to help onboard new users."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from . import views
from .const import (
    DOMAIN,
    STEP_ANALYTICS,
    STEP_CORE_CONFIG,
    STEP_INTEGRATION,
    STEP_USER,
    STEPS,
)
from .views import BaseOnboardingView, NoAuthBaseOnboardingView  # noqa: F401

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 4

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@dataclass
class OnboardingData:
    """Container for onboarding data."""

    listeners: list[Callable[[], None]]
    onboarded: bool
    steps: OnboardingStoreData


class OnboardingStoreData(TypedDict):
    """Onboarding store data."""

    done: list[str]


class OnboardingStorage(Store[OnboardingStoreData]):
    """Store onboarding data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: OnboardingStoreData,
    ) -> OnboardingStoreData:
        """Migrate to the new version."""
        # From version 1 -> 2, we automatically mark the integration step done
        if old_major_version < 2:
            old_data["done"].append(STEP_INTEGRATION)
        if old_major_version < 3:
            old_data["done"].append(STEP_CORE_CONFIG)
        if old_major_version < 4:
            old_data["done"].append(STEP_ANALYTICS)
        return old_data


@bind_hass
@callback
def async_is_onboarded(hass: HomeAssistant) -> bool:
    """Return if Home Assistant has been onboarded."""
    data: OnboardingData | None = hass.data.get(DOMAIN)
    return data is None or data.onboarded is True


@bind_hass
@callback
def async_is_user_onboarded(hass: HomeAssistant) -> bool:
    """Return if a user has been created as part of onboarding."""
    return async_is_onboarded(hass) or STEP_USER in hass.data[DOMAIN].steps["done"]


@callback
def async_add_listener(hass: HomeAssistant, listener: Callable[[], None]) -> None:
    """Add a listener to be called when onboarding is complete."""
    data: OnboardingData | None = hass.data.get(DOMAIN)

    if not data:
        # Onboarding not active
        return

    if data.onboarded:
        listener()
        return

    data.listeners.append(listener)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the onboarding component."""
    store = OnboardingStorage(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
    data: OnboardingStoreData | None
    if (data := await store.async_load()) is None:
        data = {"done": []}

    if TYPE_CHECKING:
        assert isinstance(data, dict)

    if STEP_USER not in data["done"]:
        # Users can already have created an owner account via the command line
        # If so, mark the user step as done.
        has_owner = False

        for user in await hass.auth.async_get_users():
            if user.is_owner:
                has_owner = True
                break

        if has_owner:
            data["done"].append(STEP_USER)
            await store.async_save(data)

    if set(data["done"]) == set(STEPS):
        return True

    hass.data[DOMAIN] = OnboardingData([], False, data)

    await views.async_setup(hass, data, store)

    return True
