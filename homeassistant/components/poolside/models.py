"""Data models for the Poolside integration."""

from dataclasses import dataclass, field
from typing import Any

from .const import (
    COMBINED_CONTROL_UUID_FIELD,
    CONTROL_TYPE_MAP,
    LOGGER,
    MAX_SET_POINT_FIELD,
    MEMBER_CONTROL_UUIDS_FIELD,
    MIN_SET_POINT_FIELD,
    SPEED_INCREMENTS_FIELD,
    WINTERIZED_FIELD,
    ControlType,
    GroupKind,
)


@dataclass
class PoolsideGroup:
    """A control group from Site.getControlLayout (a body of water or landscape area)."""

    uuid: str
    name: str
    kind: GroupKind | None
    body_of_water_uuid: str | None = None
    body_of_water_type: str | None = None


@dataclass
class PoolsideControl:
    """A single control, as rendered from Site.getControlLayout.

    `uuid` is this control's own identity: unique_id, ControlUUID in writes,
    and the key its own status pushes (Status/PowerState/ActualPowerState/...)
    arrive under. `ControlItemUUID` (where present) instead identifies the
    underlying PoolDevice - separate physical hardware, not the control - and
    must not be used to resolve control state.
    """

    uuid: str
    name: str
    control_type: ControlType
    group: PoolsideGroup
    raw: dict[str, Any] = field(default_factory=dict)

    def capability(self, *keys: str) -> Any | None:
        """Return the first matching capability field, tolerating casing differences."""
        for key in keys:
            if key in self.raw:
                return self.raw[key]
        return None

    @property
    def status_key(self) -> str:
        """Return the UUID that confirmed body-level telemetry is keyed on.

        Only meaningful for TEMPERATURE, which regulates a body of water
        rather than being a device in its own right (current temperature,
        supported mode lists, ...); every other control type has no separate
        telemetry source, so this is just their own UUID.
        """
        if self.control_type is ControlType.TEMPERATURE:
            return self.group.body_of_water_uuid or self.uuid
        return self.uuid

    @property
    def member_uuids(self) -> list[str]:
        """Return this combined control's member UUIDs, if it is one.

        Each physical member may report its own status independently under
        its own UUID rather than the synthetic combined UUID.
        """
        return list(self.raw.get(MEMBER_CONTROL_UUIDS_FIELD) or [])

    @property
    def winterized(self) -> bool:
        """Return True if the controller has taken this control offline for the season."""
        return bool(self.raw.get(WINTERIZED_FIELD))

    @property
    def min_set_point(self) -> float | None:
        """Return the controller-reported minimum setpoint, if any."""
        value = self.raw.get(MIN_SET_POINT_FIELD)
        return None if value is None else float(value)

    @property
    def max_set_point(self) -> float | None:
        """Return the controller-reported maximum setpoint, if any."""
        value = self.raw.get(MAX_SET_POINT_FIELD)
        return None if value is None else float(value)

    @property
    def speed_increments(self) -> list[int]:
        """Return the sorted, deduplicated list of PowerLevel values this control accepts."""
        increments = self.raw.get(SPEED_INCREMENTS_FIELD) or [100]
        return sorted({int(value) for value in increments})

    @property
    def is_variable_speed(self) -> bool:
        """Return True if this control supports more than one output level."""
        return len(self.speed_increments) > 1


def parse_control_layout(data: dict[str, Any]) -> tuple[str, list[PoolsideControl]]:
    """Parse a Site.getControlLayout response into (site name, renderable controls).

    Controls that are members of a combined control (`CombinedControlUUID` set)
    are skipped; the combined control itself (which lists `MemberControlUUIDs`)
    is rendered in their place, inheriting any layout capability fields
    (`SupportsColors`, `SpeedIncrements`, ...) it doesn't itself carry from its
    first member.
    """
    site_name = data.get("SiteName") or "Poolside"
    controls: list[PoolsideControl] = []
    for group_data in data.get("Groups", []):
        group = _parse_group(group_data)
        raw_controls = group_data.get("Controls", [])
        by_uuid = {
            control_data["UUID"]: control_data
            for control_data in raw_controls
            if control_data.get("UUID")
        }
        for control_data in raw_controls:
            combined_uuid = control_data.get(COMBINED_CONTROL_UUID_FIELD)
            if combined_uuid:
                LOGGER.debug(
                    "Skipping control %s (%s): member of combined control %s",
                    control_data.get("UUID"),
                    control_data.get("Name"),
                    combined_uuid,
                )
                continue
            member_uuids = control_data.get(MEMBER_CONTROL_UUIDS_FIELD)
            if member_uuids and (first_member := by_uuid.get(member_uuids[0])):
                control_data = {**first_member, **control_data}
            control = _parse_control(control_data, group)
            LOGGER.debug(
                "Rendering control %s (%s): type=%s status_key=%s member_uuids=%s",
                control.uuid,
                control.name,
                control.control_type,
                control.status_key,
                control.member_uuids,
            )
            controls.append(control)
    return site_name, controls


def _parse_group(data: dict[str, Any]) -> PoolsideGroup:
    uuid = data.get("UUID") or data.get("uuid")
    if not uuid:
        raise ValueError(f"Group is missing a UUID: {data}")
    name = data.get("BodyOfWaterName") or data.get("Name") or uuid
    raw_kind = data.get("Kind")
    try:
        kind = GroupKind(raw_kind) if raw_kind else None
    except ValueError:
        kind = None
    return PoolsideGroup(
        uuid=str(uuid),
        name=str(name),
        kind=kind,
        body_of_water_uuid=data.get("BodyOfWaterUUID"),
        body_of_water_type=data.get("BodyOfWaterType"),
    )


def _parse_control(data: dict[str, Any], group: PoolsideGroup) -> PoolsideControl:
    uuid = data.get("UUID") or data.get("uuid")
    if not uuid:
        raise ValueError(f"Control is missing a UUID: {data}")
    name = data.get("Name") or data.get("name") or uuid
    raw_type = str(
        data.get("ControlType") or data.get("Type") or data.get("type") or ""
    )
    try:
        control_type = ControlType(raw_type.upper())
    except ValueError:
        control_type = CONTROL_TYPE_MAP.get(raw_type.lower(), ControlType.UNKNOWN)
    return PoolsideControl(
        uuid=str(uuid),
        name=str(name),
        control_type=control_type,
        group=group,
        raw=data,
    )
