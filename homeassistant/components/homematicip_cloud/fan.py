"""Support for HomematicIP Cloud ventilation actuators."""

from typing import Any, override

from homematicip.base.functionalChannels import FunctionalChannelType
from homematicip.device import Device

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP

VENTILATION_ACTUATOR_ROLE = "VENTILATION_ACTUATOR"

STATE_VENTILATION = "VENTILATION"
STATE_NO_VENTILATION = "NO_VENTILATION"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP fans from a config entry."""
    hap = config_entry.runtime_data
    async_add_entities(
        HomematicipVentilationFan(hap, device, ch.index)
        for device in hap.home.devices
        for ch in device.functionalChannels
        # The channel type also carries dimming actuators, so the role decides.
        if ch.functionalChannelType == FunctionalChannelType.UNIVERSAL_ACTUATOR_CHANNEL
        and ch.channelRole == VENTILATION_ACTUATOR_ROLE
    )


class HomematicipVentilationFan(HomematicipGenericEntity, FanEntity):
    """Representation of a HomematicIP ventilation actuator."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, hap: HomematicipHAP, device: Device, channel: int) -> None:
        """Initialize the ventilation fan."""
        super().__init__(
            hap,
            device=device,
            channel=channel,
            channel_real_index=channel,
            post="ventilation",
            is_multi_channel=True,
            feature_id="ventilation",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the actuator is ventilating."""
        channel = self.get_channel_or_raise()
        return channel.ventilationState == STATE_VENTILATION

    @property
    @override
    def percentage(self) -> int | None:
        """Return the current ventilation level in percent."""
        channel = self.get_channel_or_raise()
        return round(channel.ventilationLevel * 100)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the ventilation level."""
        channel = self.get_channel_or_raise()
        if percentage == 0:
            await channel.async_set_ventilation_state(STATE_NO_VENTILATION)
            return
        await channel.async_set_ventilation_level(percentage / 100)

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Start ventilating, optionally at a given level."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        channel = self.get_channel_or_raise()
        await channel.async_set_ventilation_state(STATE_VENTILATION)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop ventilating."""
        channel = self.get_channel_or_raise()
        await channel.async_set_ventilation_state(STATE_NO_VENTILATION)
