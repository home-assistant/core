"""Support for HomematicIP Cloud button devices."""

from typing import override

from homematicip.base.functionalChannels import AccessAuthorizationChannel
from homematicip.device import WallMountedGarageDoorController
import voluptuous as vol

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP

DOOR_OPENER_MODELS = {"HmIP-FLC", "HmIP-FDC"}

ATTR_PIN = "pin"
SERVICE_PULL_LATCH = "pull_latch"


def _door_opener_authorization_channel(
    device: object,
) -> AccessAuthorizationChannel | None:
    """Return the AccessAuthorizationChannel routed to the door opener."""
    for channel in getattr(device, "functionalChannels", []):
        if (
            isinstance(channel, AccessAuthorizationChannel)
            and getattr(channel, "channelRole", None) == "DOOR_OPENER_ACTUATOR"
        ):
            return channel
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP button from a config entry."""
    hap = config_entry.runtime_data

    entities: list[ButtonEntity] = [
        HomematicipGarageDoorControllerButton(hap, device)
        for device in hap.home.devices
        if isinstance(device, WallMountedGarageDoorController)
    ]
    entities.extend(
        HomematicipDoorOpenerButton(hap, device, auth_channel)
        for device in hap.home.devices
        if getattr(device, "modelType", None) in DOOR_OPENER_MODELS
        and (auth_channel := _door_opener_authorization_channel(device)) is not None
    )
    async_add_entities(entities)

    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_PULL_LATCH,
        {vol.Optional(ATTR_PIN): cv.string},
        "async_pull_latch",
    )


class HomematicipButtonEntity(HomematicipGenericEntity, ButtonEntity):
    """Base class for HomematicIP buttons."""

    async def async_pull_latch(self, pin: str | None = None) -> None:
        """Pull the latch of a door opener."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="pull_latch_not_supported",
            translation_placeholders={"entity_id": self.entity_id},
        )


class HomematicipGarageDoorControllerButton(HomematicipButtonEntity):
    """Representation of the HomematicIP Wall mounted Garage Door Controller."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize a wall mounted garage door controller."""
        super().__init__(hap, device, feature_id="garage_button")
        self._attr_icon = "mdi:arrow-up-down"

    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        await self._device.send_start_impulse_async()


class HomematicipDoorOpenerButton(HomematicipButtonEntity):
    """Representation of a HomematicIP door opener (HmIP-FLC, HmIP-FDC)."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        auth_channel: AccessAuthorizationChannel,
    ) -> None:
        """Initialize the door opener button."""
        super().__init__(
            hap, device, post="Door opener", feature_id="lock_opener_button"
        )
        self._attr_icon = "mdi:door-open"
        self._auth_channel = auth_channel

    @override
    async def async_press(self) -> None:
        """Pull the latch via the access-authorization channel.

        This is the only path non-admin clients may use; the door-switch
        channel rejects them with CLIENT_ACCESS_DENIED.
        """
        await self._auth_channel.async_pull_latch()

    @override
    async def async_pull_latch(self, pin: str | None = None) -> None:
        """Pull the latch, optionally with the authorization PIN."""
        await self._auth_channel.async_pull_latch(pin)
