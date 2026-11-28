"""Base classes for Rituals Perfume Genie diffuser entities."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, override

from ritualsgenie import (
    RitualsGenieAuthenticationError,
    RitualsGenieConnectionError,
    RitualsGenieError,
    RitualsGenieHub,
    RitualsGenieHublot,
    RitualsGenieRateLimitError,
    Sensor,
)

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    RitualsConfigEntry,
    RitualsHubsCoordinator,
    RitualsSensorsCoordinator,
)

MANUFACTURER = "Rituals Cosmetics"


@callback
def async_add_diffusers(
    config_entry: RitualsConfigEntry, add_diffusers: Callable[[list[str]], None]
) -> None:
    """Add the entities of the diffusers on the account, now and later on.

    A diffuser that left the account is forgotten here, so it gets its
    entities back when it returns.
    """
    hubs = config_entry.runtime_data.hubs
    known: set[str] = set()

    @callback
    def _async_add_new() -> None:
        known.intersection_update(hubs.data)
        if new := [hublot for hublot in hubs.data if hublot not in known]:
            known.update(new)
            add_diffusers(new)

    _async_add_new()
    config_entry.async_on_unload(hubs.async_add_listener(_async_add_new))


def rituals_action[_DiffuserEntityT: DiffuserEntity, **_P](
    func: Callable[Concatenate[_DiffuserEntityT, _P], Coroutine[Any, Any, None]],
) -> Callable[Concatenate[_DiffuserEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate an action on a diffuser, to raise its errors translated.

    Rejected credentials start a reauthentication right away, instead of
    waiting for the next update to find out.
    """

    async def handler(
        self: _DiffuserEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
        except RitualsGenieAuthenticationError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except RitualsGenieRateLimitError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="rate_limited"
            ) from err
        except RitualsGenieConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="communication_error"
            ) from err
        except RitualsGenieError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err

    return handler


def _device_info(
    hub: RitualsGenieHub, hardware: RitualsGenieHublot | None
) -> DeviceInfo:
    """Return the device info of a diffuser."""
    firmware = hub.firmware.current if hub.firmware else None

    device_info = DeviceInfo(
        identifiers={(DOMAIN, hub.hublot)},
        manufacturer=MANUFACTURER,
        name=hub.name,
        sw_version=str(firmware) if firmware else None,
    )

    # Left out when unknown, so a model stored before isn't wiped.
    if hardware and hardware.device_version:
        device_info["model"] = hardware.device_version

    return device_info


def _hub_available(hubs: RitualsHubsCoordinator, hublot: str) -> bool:
    """Return if the diffusers could be fetched, and this one is available.

    That is: on the account, and not reported offline.
    """
    if not hubs.last_update_success or (hub := hubs.data.get(hublot)) is None:
        return False

    return hub.is_online is not False


class DiffuserEntity(CoordinatorEntity[RitualsHubsCoordinator]):
    """Representation of a diffuser entity, kept up to date with its state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RitualsHubsCoordinator,
        hublot: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.hublot = hublot

        self._attr_unique_id = f"{hublot}-{description.key}"
        self._attr_device_info = _device_info(
            coordinator.data[hublot], coordinator.hardware.get(hublot)
        )

    @property
    def hub(self) -> RitualsGenieHub:
        """Return the diffuser."""
        return self.coordinator.data[self.hublot]

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and _hub_available(self.coordinator, self.hublot)


class DiffuserSensorsEntity(CoordinatorEntity[RitualsSensorsCoordinator]):
    """Representation of a diffuser entity, kept up to date with its sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RitualsSensorsCoordinator,
        description: EntityDescription,
        sensor: Sensor,
    ) -> None:
        """Initialize the entity."""
        # The context tells the coordinator which sensor this entity needs.
        super().__init__(coordinator, context=sensor)
        self.entity_description = description

        hubs = coordinator.hubs
        self._attr_unique_id = f"{coordinator.hublot}-{description.key}"
        self._attr_device_info = _device_info(
            hubs.data[coordinator.hublot], hubs.hardware.get(coordinator.hublot)
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Also listen to the diffusers, for a timely availability."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.hubs.async_add_listener(self._handle_coordinator_update)
        )
        self.coordinator.async_entity_added()

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and _hub_available(self.coordinator.hubs, self.coordinator.hublot)
        )
