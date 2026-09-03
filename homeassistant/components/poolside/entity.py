"""Base entity for Poolside controls."""

import json
from typing import Any, override

from aiopoolside import (
    PoolsideClient,
    PoolsideCommandError,
    PoolsideConnectionError,
    PoolsideControl,
    PoolsideDevice,
    PoolsideGroup,
)
from aiopoolside.const import (
    ACTUAL_POWER_STATE_FIELD,
    DISABLED_REASONS_FIELD,
    POWER_STATE_FIELD,
    STATUS_FIELD,
    UNKNOWN_POWER_STATE,
    VARIABLE_SPEED_CONTROL_TYPES,
    ControlType,
    SiteMode,
)

from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LOGGER


def control_platform(control: PoolsideControl) -> Platform:
    """Return the HA platform this control is rendered on.

    A control's platform can change between layouts (e.g. a filter
    reconfigured from single- to variable-speed moves from switch to
    fan), so this is the single source of truth for both entity setup
    and stale-registry pruning.
    """
    if control.control_type is ControlType.TEMPERATURE:
        return Platform.CLIMATE
    if control.control_type is ControlType.LIGHT:
        return Platform.LIGHT
    if (
        control.control_type in VARIABLE_SPEED_CONTROL_TYPES
        and control.is_variable_speed
    ):
        return Platform.FAN
    return Platform.SWITCH


def confirmed_status(
    client: PoolsideClient, control: PoolsideControl, field: str
) -> Any:
    """Return the controller-confirmed value of a field for this control.

    Status pushes win over the connect-time control layout, since they
    reflect changes made after the layout was fetched. Pushes have been
    observed keyed by the group's BodyOfWaterUUID (`status_key`), by the
    control's own UUID, and - for combined controls - by a member's UUID,
    so every candidate key is checked.
    """
    for key in (control.status_key, control.uuid, *control.member_uuids):
        if (value := client.get_status(key, field)) is not None:
            return value
    return control.capability(field)


def confirmed_json(client: PoolsideClient, control: PoolsideControl, field: str) -> Any:
    """Return a confirmed value that may arrive JSON-encoded inside a string.

    Capability fields (supported-mode lists, light catalogs, ...) are native
    JSON in the control layout but arrive as JSON documents encoded inside
    the string value in status pushes (e.g. '["HEAT", "COOL"]'), so both
    shapes are accepted.
    """
    value = confirmed_status(client, control, field)
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        LOGGER.warning("%s: unparsable %s: %r", control.name, field, value)
        return None


class PoolsideBaseEntity(Entity):
    """Base class for all Poolside entities: connectivity and status pushes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: PoolsideClient) -> None:
        """Set up the entity on a client connection."""
        self._client = client

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


class PoolsideGroupEntity(PoolsideBaseEntity):
    """Base class for entities attached to a control group's device."""

    def __init__(self, client: PoolsideClient, group: PoolsideGroup) -> None:
        """Set up the entity on the group's device."""
        super().__init__(client)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, group.uuid)},
            name=group.name,
            manufacturer="Poolside",
            model=group.body_of_water_type or group.kind,
        )


class PoolsideDeviceEntity(PoolsideBaseEntity):
    """Base class for entities attached to a physical pool device.

    The device registry entry itself is registered up front during setup
    (pool devices exist even before any telemetry arrives), so only the
    identifiers are needed here to attach to it.
    """

    def __init__(self, client: PoolsideClient, device: PoolsideDevice) -> None:
        """Set up the entity on the pool device's sub-device."""
        super().__init__(client)
        self._device = device
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device.uuid)})

    @override
    def _status_keys(self) -> set[str]:
        """Return the pool device's key its telemetry arrives under."""
        return {self._device.uuid}


class PoolsideEntity(PoolsideGroupEntity):
    """Base class for entities backed by a single Poolside control."""

    # _attr_name wins over a translated name, so entities whose name comes
    # from their translation_key (rather than directly from the control's
    # name) flip this to keep _attr_name unset. A translation_key alone is
    # no signal - it may exist purely for icon translations.
    _use_translated_name = False

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the entity for a given control."""
        super().__init__(client, control.group)
        self._control = control
        self._attr_unique_id = f"{client.controller_uuid}_{control.uuid}"
        if not self._use_translated_name:
            self._attr_name = control.name

    @property
    @override
    def available(self) -> bool:
        """Return True if connected and the control isn't hard-disabled.

        INSTALLER mode takes the whole site out of service from the user's
        point of view, so every control goes unavailable while it lasts.
        A control is otherwise only out of service when the controller
        reports a DisabledReasons entry for it; Status=DISABLED alone is
        deliberately ignored - it's a suggestion that activating the control
        will turn something else off, not a lockout.
        """
        return (
            super().available
            and self._client.site_mode != SiteMode.INSTALLER
            and not self._control.winterized
            and not self._disabled_reasons()
        )

    def _disabled_reasons(self) -> list[str]:
        """Return the hard reasons this control is out of service.

        "WINTERIZED", "FREEZE_PROTECT", or the UUID of the pool cover
        holding it closed; empty when the control is operable.
        """
        value = self._confirmed_json(DISABLED_REASONS_FIELD)
        if not isinstance(value, list):
            return []
        return [str(reason) for reason in value]

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
        """Return a confirmed telemetry/capability value pushed by the controller.

        For read-only telemetry like current temperature or supported mode
        lists; checks every key the value may arrive under.
        """
        return confirmed_status(self._client, self._control, field)

    def _confirmed_json(self, field: str) -> Any:
        """Return a confirmed value that may arrive JSON-encoded in a string."""
        return confirmed_json(self._client, self._control, field)

    def _confirmed_json_list(self, field: str) -> list[Any]:
        """Return a confirmed JSON list capability, or [] if absent or malformed."""
        value = self._confirmed_json(field)
        return value if isinstance(value, list) else []

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
        """Write this control's desired state, translating protocol errors.

        The controller only accepts desired-state writes while the site is
        in NORMAL mode, so any other known mode fails fast with a clear
        message instead of a generic rejection.
        """
        mode = self._client.site_mode
        if mode is not None and mode != SiteMode.NORMAL:
            raise HomeAssistantError(
                f"The Poolside controller is in {mode} mode; {self.name} can only"
                " be changed while it is in NORMAL mode"
            )
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
        """Return every key this control's state may arrive under.

        Includes the site UUID (when known) so availability updates as soon
        as the site-wide Mode changes.
        """
        keys = {
            self._control.status_key,
            self._control.uuid,
            *self._control.member_uuids,
        }
        if (site_uuid := self._client.site_uuid) is not None:
            keys.add(site_uuid)
        return keys
