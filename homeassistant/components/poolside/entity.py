"""Base entity for Poolside controls."""

from typing import Any, override

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .client import PoolsideClient, PoolsideCommandError, PoolsideConnectionError
from .const import (
    ACTUAL_POWER_STATE_FIELD,
    DOMAIN,
    LOGGER,
    POWER_STATE_FIELD,
    STATUS_FIELD,
    UNKNOWN_POWER_STATE,
    StatusState,
)
from .models import PoolsideControl, PoolsideGroup


class PoolsideGroupEntity(Entity):
    """Base class for entities attached to a control group's device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: PoolsideClient, group: PoolsideGroup) -> None:
        """Set up the entity on the group's device."""
        self._client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, group.uuid)},
            name=group.name,
            manufacturer="Poolside",
            model=group.body_of_water_type or group.kind,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the controller connection is up."""
        return self._client.available

    def _status_keys(self) -> set[str]:
        """Return the status keys whose pushes should refresh this entity."""
        return set()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to status pushes for this entity and connection changes."""
        for key in self._status_keys():
            self.async_on_remove(
                self._client.subscribe_status(key, self.async_write_ha_state)
            )
        self.async_on_remove(
            self._client.subscribe_connection(
                lambda _connected: self.async_write_ha_state()
            )
        )


class PoolsideEntity(PoolsideGroupEntity):
    """Base class for entities backed by a single Poolside control."""

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the entity for a given control."""
        super().__init__(client, control.group)
        self._control = control
        self._attr_unique_id = f"{client.controller_uuid}_{control.uuid}"
        self._attr_name = control.name

    @property
    @override
    def available(self) -> bool:
        """Return True if connected and the control isn't disabled or winterized."""
        return (
            super().available
            and not self._control.winterized
            and self._power_state() != StatusState.DISABLED
        )

    def _power_state(self) -> Any:
        """Return this control's on/off/disabled state, ground truth first.

        Observed on the wire keyed by the control's own UUID, under either
        `ActualPowerState` (ground truth), `PowerState` (what was requested),
        or plain `Status` - which fields get pushed appears to vary by
        control. A combined control's members may also report their own
        state independently under their own UUIDs rather than the synthetic
        combined UUID, so those are checked too. Checked in that field order
        (ground truth first) across every candidate key, with our own
        optimistic write echo as the final, least-trusted fallback.

        Deliberately does NOT check `status_key`: for non-TEMPERATURE
        controls that resolves to the underlying PoolDevice's UUID, which is
        separate physical hardware, not this control - its status must never
        be used to resolve control state, even though it can look tempting
        (e.g. it happens to track the control's state most of the time).

        Some hardware can't confirm ground truth at all: its ActualPowerState
        sits at the literal string "UNKNOWN" forever. That's a "no data"
        sentinel, not a real value, so it's skipped just like a missing field.
        """
        client = self._client
        control = self._control
        keys = (control.uuid, *control.member_uuids)
        for status_field in (ACTUAL_POWER_STATE_FIELD, POWER_STATE_FIELD, STATUS_FIELD):
            for key in keys:
                value = client.get_status(key, status_field)
                if value is not None and value != UNKNOWN_POWER_STATE:
                    LOGGER.debug(
                        "%s (%s) power_state resolved via %s.%s = %r",
                        control.uuid,
                        control.name,
                        key,
                        status_field,
                        value,
                    )
                    return value
        LOGGER.debug(
            "%s (%s) power_state: no data found under any of %s",
            control.uuid,
            control.name,
            keys,
        )
        return None

    def _confirmed(self, field: str) -> Any:
        """Return a confirmed body-level telemetry value pushed by the controller.

        Keyed by `status_key` (the group's BodyOfWaterUUID for TEMPERATURE,
        this control's own UUID otherwise) - for read-only telemetry like
        current temperature or supported mode lists.
        """
        return self._client.get_status(self._control.status_key, field)

    def _desired(self, field: str) -> Any:
        """Return this control's last-written (optimistic) desired-state value.

        Keyed by the control's own UUID. Fields like PowerLevel, SetPoint,
        and LightName aren't (as far as observed) pushed back by the
        controller, so this reflects our own last successful write, not a
        server-confirmed value. On/off specifically is pushed - use
        `_power_state()` for that instead of `_desired(STATUS_FIELD)`.
        """
        return self._client.get_status(self._control.uuid, field)

    async def _async_write_state(self, **fields: Any) -> None:
        """Write this control's desired state, translating protocol errors."""
        try:
            await self._client.async_set_desired_state(self._control.uuid, **fields)
        except PoolsideCommandError as err:
            raise HomeAssistantError(
                f"The controller rejected the request for {self.name}: {err}"
            ) from err
        except PoolsideConnectionError as err:
            raise HomeAssistantError(
                f"Lost connection to the Poolside controller while updating {self.name}"
            ) from err

    @override
    def _status_keys(self) -> set[str]:
        """Return every key this control's state may arrive under."""
        return {
            self._control.status_key,
            self._control.uuid,
            *self._control.member_uuids,
        }
