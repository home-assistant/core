"""Provides triggers for Fumis pellet stoves."""

from typing import override

from fumis import StoveAlert
import probatio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, async_noop, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType

from .const import DOMAIN
from .coordinator import (
    SIGNAL_COORDINATOR_UPDATED,
    FumisConfigEntry,
    FumisDataUpdateCoordinator,
)

_CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS): {
            probatio.Required(ATTR_DEVICE_ID): probatio.All(
                probatio.EnsureList(), probatio.Length(min=1), [cv.string]
            ),
        },
    }
)


def _get_alert(
    coordinator: FumisDataUpdateCoordinator,
) -> StoveAlert | UndefinedType | None:
    """Return the active stove alert, or UNDEFINED when it is not known.

    Like entity triggers ignore unavailable and unknown states, a failed
    update or an unrecognized alert code is never compared against.
    """
    if not coordinator.last_update_success:
        return UNDEFINED

    if (alert := coordinator.data.controller.stove_alert) is StoveAlert.UNKNOWN:
        return UNDEFINED

    return alert


class FuelBecameLowTrigger(Trigger):
    """Trigger when a stove reports its fuel became low.

    The stove reports a single alert at a time, so another alert, like the
    door being open, can hide the low fuel alert. Other alerts therefore
    leave the tracked alert as it was, instead of counting as a change.
    """

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        config = _CONFIG_SCHEMA(config)
        for device_id in config[CONF_OPTIONS][ATTR_DEVICE_ID]:
            _, entry = dr.async_get_device_and_config_entry_for_domain(
                hass, device_id, domain=DOMAIN
            )
            if entry is None:
                raise probatio.Invalid(f"Device {device_id} is not a Fumis stove")

        return config

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        assert config.options is not None
        self._device_ids: list[str] = config.options[ATTR_DEVICE_ID]

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        unsubscribes: list[CALLBACK_TYPE] = []
        for device_id in self._device_ids:
            device, entry = dr.async_get_device_and_config_entry_for_domain(
                self._hass, device_id, domain=DOMAIN
            )
            if device is None or entry is None:
                continue

            unsubscribes.append(
                self._async_track_stove(device_id, device, entry, run_action)
            )

        @callback
        def async_remove() -> None:
            """Stop tracking the stoves."""
            for unsubscribe in unsubscribes:
                unsubscribe()

        return async_remove

    @callback
    def _async_track_stove(
        self,
        device_id: str,
        device: dr.AnyDeviceEntry,
        entry: FumisConfigEntry,
        run_action: TriggerActionRunner,
    ) -> CALLBACK_TYPE:
        """Track the low fuel alert of a single stove."""
        description = f"fuel became low on {device.name_by_user or device.name}"
        tracked_coordinator: FumisDataUpdateCoordinator | None = None
        remove_coordinator_listener: CALLBACK_TYPE | None = None
        previous_alert: StoveAlert | UndefinedType | None = UNDEFINED

        @callback
        def async_track_coordinator(coordinator: FumisDataUpdateCoordinator) -> None:
            """Keep the coordinator of the stove polling while attached."""
            nonlocal tracked_coordinator, remove_coordinator_listener
            if remove_coordinator_listener is not None:
                remove_coordinator_listener()

            # A coordinator only polls while something listens to it, and the
            # stove might not have any enabled entities doing that.
            tracked_coordinator = coordinator
            remove_coordinator_listener = coordinator.async_add_listener(async_noop)

        if entry.state is ConfigEntryState.LOADED:
            async_track_coordinator(entry.runtime_data)
            # Another alert could be hiding the low fuel alert already.
            if (alert := _get_alert(entry.runtime_data)) in (
                StoveAlert.LOW_FUEL,
                None,
            ):
                previous_alert = alert

        @callback
        def async_coordinator_updated(
            coordinator: FumisDataUpdateCoordinator,
        ) -> None:
            """Compare the stove alert against the previous update."""
            nonlocal previous_alert

            # A new coordinator means the entry was reloaded. Its entities
            # were removed and added again, so there is nothing to compare
            # against, just like for an entity trigger.
            if coordinator is not tracked_coordinator:
                async_track_coordinator(coordinator)
                previous_alert = UNDEFINED

            alert = _get_alert(coordinator)
            if alert not in (StoveAlert.LOW_FUEL, None, UNDEFINED):
                return

            if previous_alert is None and alert is StoveAlert.LOW_FUEL:
                run_action({ATTR_DEVICE_ID: device_id}, description)

            previous_alert = alert

        remove_dispatcher = async_dispatcher_connect(
            self._hass,
            SIGNAL_COORDINATOR_UPDATED.format(entry.entry_id),
            async_coordinator_updated,
        )

        @callback
        def async_remove() -> None:
            """Stop tracking the stove."""
            remove_dispatcher()
            if remove_coordinator_listener is not None:
                remove_coordinator_listener()

        return async_remove


TRIGGERS: dict[str, type[Trigger]] = {
    "fuel_became_low": FuelBecameLowTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for Fumis pellet stoves."""
    return TRIGGERS
