"""Support for HomematicIP Cloud button devices."""

from homematicip.base.functionalChannels import AccessAuthorizationChannel
from homematicip.device import WallMountedGarageDoorController

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP


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
        HomematicipFullFlushLockControllerButton(hap, device, auth_channel)
        for device in hap.home.devices
        if getattr(device, "modelType", None) == "HmIP-FLC"
        and (auth_channel := _door_opener_authorization_channel(device)) is not None
    )
    async_add_entities(entities)


class HomematicipGarageDoorControllerButton(HomematicipGenericEntity, ButtonEntity):
    """Representation of the HomematicIP Wall mounted Garage Door Controller."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize a wall mounted garage door controller."""
        super().__init__(hap, device, feature_id="garage_button")
        self._attr_icon = "mdi:arrow-up-down"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._device.send_start_impulse_async()


class HomematicipFullFlushLockControllerButton(HomematicipGenericEntity, ButtonEntity):
    """Representation of the HomematicIP full flush lock controller opener."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        auth_channel: AccessAuthorizationChannel,
    ) -> None:
        """Initialize the full flush lock controller opener button."""
        super().__init__(
            hap, device, post="Door opener", feature_id="lock_opener_button"
        )
        self._attr_icon = "mdi:door-open"
        self._auth_channel = auth_channel

    async def async_press(self) -> None:
        """Handle the button press.

        Pulls the latch via the device's ACCESS_AUTHORIZATION_CHANNEL with
        role DOOR_OPENER_ACTUATOR. The cloud routes the impulse through the
        access-authorization profile, which is the only endpoint non-admin
        clients are allowed to invoke (calling the underlying door-switch
        channel's start_impulse fails with CLIENT_ACCESS_DENIED).
        """
        await self._auth_channel.async_pull_latch()
