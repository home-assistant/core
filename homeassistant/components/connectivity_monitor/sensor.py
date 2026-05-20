"""Sensor platform for Connectivity Monitor integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import ip_address as _parse_ip_address
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    bluetooth as bluetooth_helpers,
    esphome as esphome_helpers,
    matter as matter_helpers,
    network as network_helpers,
    zha as zha_helpers,
)
from .const import (
    AD_DC_PORTS,
    CONF_ALERT_ACTION,
    CONF_ALERT_ACTION_DELAY,
    CONF_ALERT_DELAY,
    CONF_ALERT_GROUP,
    CONF_BLUETOOTH_ADDRESS,
    CONF_ESPHOME_DEVICE_ID,
    CONF_HOST,
    CONF_INACTIVE_TIMEOUT,
    CONF_MATTER_NODE_ID,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TARGETS,
    CONF_ZHA_IEEE,
    DEFAULT_ALERT_ACTION_DELAY,
    DEFAULT_ALERT_DELAY,
    DEFAULT_INACTIVE_TIMEOUT,
    DOMAIN,
    NON_NETWORK_PROTOCOLS,
    PROTOCOL_AD_DC,
    PROTOCOL_BLUETOOTH,
    PROTOCOL_ESPHOME,
    PROTOCOL_ICMP,
    PROTOCOL_MATTER,
    PROTOCOL_TCP,
    PROTOCOL_ZHA,
    VERSION,
)
from .coordinator import ConnectivityMonitorConfigEntry, ConnectivityMonitorCoordinator

NetworkProbe = network_helpers.NetworkProbe
async_get_bluetooth_device_details = (
    bluetooth_helpers.async_get_bluetooth_device_details
)
async_get_esphome_device_active = esphome_helpers.async_get_esphome_device_active
async_get_matter_device_active = matter_helpers.async_get_matter_device_active
async_get_zha_device_last_seen = zha_helpers.async_get_zha_device_last_seen

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant,
    entry: ConnectivityMonitorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Connectivity Monitor sensors."""
    _LOGGER.debug(
        "Starting setup of Connectivity Monitor entry with data: %s", entry.data
    )

    config_data = dict(entry.data)
    targets = config_data[CONF_TARGETS]
    _LOGGER.debug("Targets to process: %s", targets)

    # Separate ZHA targets from regular network targets
    network_targets = [
        t for t in targets if t.get(CONF_PROTOCOL) not in NON_NETWORK_PROTOCOLS
    ]
    zha_targets = [t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_ZHA]
    matter_targets = [t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_MATTER]
    esphome_targets = [t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME]
    bluetooth_targets = [
        t for t in targets if t.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH
    ]

    coordinator = entry.runtime_data.coordinator
    alert_handler = entry.runtime_data.alert_handler

    # Get existing entities
    entity_registry = er.async_get(hass)
    existing_entities = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    new_unique_ids: set[str] = set()
    entities: list[SensorEntity] = []

    # Group network targets by host
    host_targets: dict[str, list[dict]] = {}
    for target in network_targets:
        host = target[CONF_HOST]
        if host not in host_targets:
            host_targets[host] = []
        host_targets[host].append(target)

    _LOGGER.debug(
        "Grouped targets by host: %s",
        {
            host: [t.get(CONF_PROTOCOL) for t in targets]
            for host, targets in host_targets.items()
        },
    )

    # Process each network host
    for host, host_target_list in host_targets.items():
        _LOGGER.debug(
            "Processing host %s with targets: %s",
            host,
            [f"{t[CONF_PROTOCOL]}:{t.get(CONF_PORT, 'N/A')}" for t in host_target_list],
        )

        ad_targets = []

        # Create sensors for each target
        for target in host_target_list:
            try:
                _LOGGER.debug(
                    "Creating individual sensor for target: Protocol=%s, Port=%s",
                    target[CONF_PROTOCOL],
                    target.get(CONF_PORT, "N/A"),
                )

                if (
                    target[CONF_PROTOCOL] == PROTOCOL_TCP
                    and target.get(CONF_PORT) in AD_DC_PORTS
                ):
                    _LOGGER.debug(
                        "Adding target to AD overview for port %s",
                        target.get(CONF_PORT),
                    )
                    ad_targets.append(target)

                sensor = ConnectivitySensor(coordinator, target)
                entities.append(sensor)
                if sensor.unique_id is not None:
                    new_unique_ids.add(sensor.unique_id)
                _LOGGER.debug(
                    "Created individual sensor: entity_id=%s, unique_id=%s",
                    sensor.entity_id,
                    sensor.unique_id,
                )

            except Exception:
                _LOGGER.exception(
                    "Error creating individual sensor for target %s", target
                )

        # Create overview sensors
        if host_target_list:
            try:
                first_target = host_target_list[0]
                device_name = first_target.get("device_name", first_target[CONF_HOST])

                _LOGGER.debug("Creating overview sensor for device: %s", device_name)
                overview = OverviewSensor(coordinator, first_target, host_target_list)
                entities.append(overview)
                if overview.unique_id is not None:
                    new_unique_ids.add(overview.unique_id)
                _LOGGER.debug(
                    "Created overview sensor: entity_id=%s, unique_id=%s",
                    overview.entity_id,
                    overview.unique_id,
                )

                # Pass alert_handler into overview sensor so it can self-register
                # in async_added_to_hass using its final HA-assigned entity_id.
                overview._alert_handler = alert_handler  # noqa: SLF001

                # Create AD overview if needed
                if ad_targets:
                    _LOGGER.debug(
                        "Creating AD overview sensor with %d AD targets",
                        len(ad_targets),
                    )
                    ad_overview = ADOverviewSensor(
                        coordinator, first_target, ad_targets
                    )
                    entities.append(ad_overview)
                    if ad_overview.unique_id is not None:
                        new_unique_ids.add(ad_overview.unique_id)
                    _LOGGER.debug(
                        "Created AD overview sensor: entity_id=%s, unique_id=%s",
                        ad_overview.entity_id,
                        ad_overview.unique_id,
                    )

            except Exception:
                _LOGGER.exception("Error creating overview sensors for host %s", host)

        _LOGGER.debug(
            "Completed processing for host %s. Created %d sensors", host, len(entities)
        )

    # Process ZHA device targets
    for target in zha_targets:
        try:
            zha_sensor = ZHASensor(coordinator, target)
            entities.append(zha_sensor)
            if zha_sensor.unique_id is not None:
                new_unique_ids.add(zha_sensor.unique_id)
            _LOGGER.debug(
                "Created ZHA sensor: entity_id=%s, unique_id=%s",
                zha_sensor.entity_id,
                zha_sensor.unique_id,
            )
            # Pass alert_handler into ZHA sensor so it can self-register in
            # async_added_to_hass using its final HA-assigned entity_id.
            zha_sensor._alert_handler = alert_handler  # noqa: SLF001
        except Exception:
            _LOGGER.exception("Error creating ZHA sensor for target %s", target)

    # Process Matter device targets
    for target in matter_targets:
        try:
            matter_sensor = MatterSensor(coordinator, target)
            entities.append(matter_sensor)
            if matter_sensor.unique_id is not None:
                new_unique_ids.add(matter_sensor.unique_id)
            _LOGGER.debug(
                "Created Matter sensor: entity_id=%s, unique_id=%s",
                matter_sensor.entity_id,
                matter_sensor.unique_id,
            )
            matter_sensor._alert_handler = alert_handler  # noqa: SLF001
        except Exception:
            _LOGGER.exception("Error creating Matter sensor for target %s", target)

    # Process ESPHome device targets
    for target in esphome_targets:
        try:
            esphome_sensor = ESPHomeSensor(coordinator, target)
            entities.append(esphome_sensor)
            if esphome_sensor.unique_id is not None:
                new_unique_ids.add(esphome_sensor.unique_id)
            _LOGGER.debug(
                "Created ESPHome sensor: entity_id=%s, unique_id=%s",
                esphome_sensor.entity_id,
                esphome_sensor.unique_id,
            )
            esphome_sensor._alert_handler = alert_handler  # noqa: SLF001
        except Exception:
            _LOGGER.exception("Error creating ESPHome sensor for target %s", target)

    # Process Bluetooth device targets
    for target in bluetooth_targets:
        try:
            bt_sensor = BluetoothSensor(coordinator, target)
            entities.append(bt_sensor)
            if bt_sensor.unique_id is not None:
                new_unique_ids.add(bt_sensor.unique_id)
            _LOGGER.debug(
                "Created Bluetooth sensor: entity_id=%s, unique_id=%s",
                bt_sensor.entity_id,
                bt_sensor.unique_id,
            )
            bt_sensor._alert_handler = alert_handler  # noqa: SLF001
        except Exception:
            _LOGGER.exception("Error creating Bluetooth sensor for target %s", target)

    # Remove old entities
    for entity in existing_entities:
        if entity.unique_id not in new_unique_ids:
            _LOGGER.debug(
                "Removing old entity: %s (unique_id: %s)",
                entity.entity_id,
                entity.unique_id,
            )
            entity_registry.async_remove(entity.entity_id)

    # Remove orphaned devices — any device that references this config entry
    # but has no remaining entities belonging to it. This covers both our own
    # DOMAIN devices (network monitors) and shared devices (ZHA/Matter) where
    # our diagnostic sensor was removed but the config-entry link was not.
    device_registry = dr.async_get(hass)
    for device_entry in list(device_registry.devices.values()):
        if entry.entry_id not in device_entry.config_entries:
            continue
        entry_entity_ids = {
            e.entity_id
            for e in er.async_entries_for_device(entity_registry, device_entry.id)
            if e.config_entry_id == entry.entry_id
        }
        if not entry_entity_ids:
            _LOGGER.debug(
                "Removing orphaned device: %s (%s)", device_entry.name, device_entry.id
            )
            if device_entry.config_entries == {entry.entry_id}:
                # Only our integration owns this device — safe to delete entirely.
                device_registry.async_remove_device(device_entry.id)
            else:
                # Device is shared with another integration (e.g. ZHA/Matter).
                # Only remove our association so the device remains intact.
                device_registry.async_update_device(
                    device_entry.id, remove_config_entry_id=entry.entry_id
                )

    _LOGGER.debug(
        "Final entities to be added: %s",
        [{"entity_id": e.entity_id, "unique_id": e.unique_id} for e in entities],
    )

    if entities:
        _LOGGER.debug("Adding %d entities to Home Assistant", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.error("No entities were created during setup!")


class AlertHandler:
    """Handle alert notifications for connectivity status."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the alert handler."""
        self.hass = hass
        self._last_disconnected: dict[str, datetime | None] = {}
        self._notified: dict[str, bool] = {}
        self._action_fired: dict[str, bool] = {}
        self._callbacks: dict[str, Any] = {}
        self._targets: dict[str, dict] = {}  # Store target info for each entity
        # Tracks the timestamp when a device first entered a recovery state.
        # We require the recovery to persist for at least one full timer cycle
        # before clearing alert tracking, so brief false-positive "Connected"
        # states don't reset the alert delay countdown.
        self._recovering_since: dict = {}
        self._check_timer: Any = None
        self._setup_alert_timer()
        _LOGGER.debug("AlertHandler initialized")

    def _setup_alert_timer(self) -> None:
        """Set up periodic timer to check alerts."""

        async def async_check(_now=None):
            """Wrapper for async check."""
            await self._check_alerts()

        self._check_timer = async_track_time_interval(
            self.hass, async_check, timedelta(minutes=1)
        )

    async def async_cleanup(self) -> None:
        """Cancel the periodic timer and all state-change callbacks."""
        if self._check_timer:
            self._check_timer()
            self._check_timer = None
        for unsubscribe in self._callbacks.values():
            unsubscribe()
        self._callbacks.clear()

    async def _check_alerts(self) -> None:  # noqa: C901
        """Check all monitored entities for alerts."""
        current_time = datetime.now()

        # Safety net: pick up any entity that is already in a problem state
        # but whose state-change event may have been missed (e.g., already
        # disconnected when HA loaded).  Only start tracking here, the main
        # loop below will handle the delay check on the *next* timer tick.
        for eid, tgt in self._targets.items():
            if eid in self._last_disconnected:
                continue
            is_zha_chk = tgt.get(CONF_PROTOCOL) == PROTOCOL_ZHA
            is_inactive_chk = tgt.get(CONF_PROTOCOL) in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            )
            problem_states_chk = (
                ["Inactive"]
                if is_inactive_chk
                else ["Disconnected", "Not Connected", "Partially Connected"]
            )
            cur_state = self.hass.states.get(eid)
            if cur_state and cur_state.state in problem_states_chk:
                self._last_disconnected[eid] = current_time
                self._notified[eid] = self._notified.get(eid, False)
                self._action_fired[eid] = self._action_fired.get(eid, False)
                if tgt.get(CONF_PROTOCOL) == PROTOCOL_MATTER:
                    ident = tgt.get(CONF_MATTER_NODE_ID, tgt.get(CONF_HOST, eid))
                elif tgt.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME:
                    ident = tgt.get(CONF_ESPHOME_DEVICE_ID, tgt.get(CONF_HOST, eid))
                elif tgt.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH:
                    ident = tgt.get(CONF_BLUETOOTH_ADDRESS, tgt.get(CONF_HOST, eid))
                elif is_zha_chk:
                    ident = tgt.get(CONF_ZHA_IEEE, tgt.get(CONF_HOST, eid))
                else:
                    ident = tgt.get(CONF_HOST, eid)
                _LOGGER.info(
                    "Connectivity Monitor: safety-net — detected %s already in state '%s', started tracking",
                    tgt.get("device_name", ident),
                    cur_state.state,
                )

        for entity_id, disconnect_time in list(self._last_disconnected.items()):
            if entity_id not in self._targets:
                continue
            if disconnect_time is None:
                continue

            target = self._targets[entity_id]
            is_zha = target.get(CONF_PROTOCOL) == PROTOCOL_ZHA
            is_inactive = target.get(CONF_PROTOCOL) in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            )
            problem_states = (
                ["Inactive"]
                if is_inactive
                else ["Disconnected", "Not Connected", "Partially Connected"]
            )
            recovery_state = "Active" if is_inactive else "Connected"
            if target.get(CONF_PROTOCOL) == PROTOCOL_MATTER:
                identifier = target.get(CONF_MATTER_NODE_ID, target[CONF_HOST])
            elif target.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME:
                identifier = target.get(CONF_ESPHOME_DEVICE_ID, target[CONF_HOST])
            elif target.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH:
                identifier = target.get(CONF_BLUETOOTH_ADDRESS, target[CONF_HOST])
            elif is_zha:
                identifier = target.get(CONF_ZHA_IEEE, target[CONF_HOST])
            else:
                identifier = target[CONF_HOST]
            device_name = target.get("device_name", identifier)
            elapsed_minutes = (current_time - disconnect_time).total_seconds() / 60

            state = self.hass.states.get(entity_id)
            current_state = state.state if state else "unknown"

            # Handle pending recovery confirmation
            if entity_id in self._recovering_since:
                if current_state != recovery_state:
                    # Device dropped back into problem state — cancel recovery
                    self._recovering_since.pop(entity_id, None)
                    _LOGGER.info(
                        "Connectivity Monitor: %s dropped back to '%s' — recovery cancelled",
                        device_name,
                        current_state,
                    )
                else:
                    recovery_held = (
                        current_time - self._recovering_since[entity_id]
                    ).total_seconds()
                    if recovery_held >= 60:
                        _LOGGER.info(
                            "Connectivity Monitor: recovery confirmed for %s after %.0fs",
                            device_name,
                            recovery_held,
                        )
                        cur_alert_group = target.get(CONF_ALERT_GROUP)
                        cur_alert_action = target.get(CONF_ALERT_ACTION)
                        recover_label = "active again" if is_inactive else "connected"
                        if self._notified.get(entity_id) and cur_alert_group:
                            message = f"✅ Device {device_name} ({identifier}) has recovered and is now {recover_label}"
                            await self._async_send_notification(
                                cur_alert_group, message
                            )
                        if self._action_fired.get(entity_id) and cur_alert_action:
                            offline_minutes = (
                                current_time - disconnect_time
                            ).total_seconds() / 60
                            recovery_variables = {
                                "device_name": device_name,
                                "device_address": identifier,
                                "last_online": disconnect_time.strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "minutes_offline": int(offline_minutes),
                                "hours_offline": round(offline_minutes / 60, 1),
                                "recovered": True,
                            }
                            await self._async_trigger_action(
                                cur_alert_action, recovery_variables
                            )
                        self._last_disconnected.pop(entity_id, None)
                        self._recovering_since.pop(entity_id, None)
                        self._notified[entity_id] = False
                        self._action_fired[entity_id] = False
                    else:
                        _LOGGER.info(
                            "Connectivity Monitor: %s recovery pending (%.0fs / 60s held)",
                            device_name,
                            recovery_held,
                        )
                continue

            _LOGGER.info(
                "Connectivity Monitor: timer — %s state='%s' elapsed=%.1f min "
                "(action_delay=%s min, action=%s, action_fired=%s)",
                device_name,
                current_state,
                elapsed_minutes,
                target.get(CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY),
                target.get(CONF_ALERT_ACTION, "none"),
                self._action_fired.get(entity_id, False),
            )

            if not state or state.state not in problem_states:
                continue

            state_label = "inactive" if is_inactive else state.state.lower()

            # Build context variables passed to automation/script triggers
            last_online = disconnect_time.strftime("%Y-%m-%d %H:%M:%S")
            if is_zha:
                zha_last_seen = state.attributes.get("last_seen")
                if zha_last_seen:
                    last_online = zha_last_seen
            context_variables = {
                "device_name": device_name,
                "device_address": identifier,
                "last_online": last_online,
                "minutes_offline": int(elapsed_minutes),
                "hours_offline": round(elapsed_minutes / 60, 1),
            }

            # Notification alert
            if not self._notified.get(entity_id, False):
                alert_group = target.get(CONF_ALERT_GROUP)
                alert_delay = target.get(CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY)
                if alert_group and elapsed_minutes >= alert_delay:
                    message = (
                        f"❌ Device {device_name} ({identifier}) has been "
                        f"{state_label} for {int(elapsed_minutes)} minutes"
                    )
                    await self._async_send_notification(alert_group, message)
                    self._notified[entity_id] = True
                    _LOGGER.debug(
                        "Notification sent for %s after %.1f minutes",
                        device_name,
                        elapsed_minutes,
                    )

            # Action alert
            if not self._action_fired.get(entity_id, False):
                alert_action = target.get(CONF_ALERT_ACTION)
                action_delay = target.get(
                    CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
                )
                _LOGGER.info(
                    "Connectivity Monitor: action check for %s — action='%s' elapsed=%.1f delay=%s",
                    device_name,
                    alert_action or "none",
                    elapsed_minutes,
                    action_delay,
                )
                if alert_action and elapsed_minutes >= action_delay:
                    await self._async_trigger_action(alert_action, context_variables)
                    self._action_fired[entity_id] = True
                    _LOGGER.info(
                        "Connectivity Monitor: action triggered for %s after %.1f minutes",
                        device_name,
                        elapsed_minutes,
                    )

    async def _async_trigger_action(
        self, action_entity_id: str, variables: dict | None = None
    ) -> None:
        """Trigger an automation or script via a custom event so variables are accessible."""
        try:
            event_type = "connectivity_monitor_alert"
            event_data = dict(variables) if variables else {}
            event_data["action_entity_id"] = action_entity_id

            _LOGGER.warning(
                "Connectivity Monitor: firing event '%s' with data %s",
                event_type,
                event_data,
            )
            self.hass.bus.async_fire(event_type, event_data)
            _LOGGER.info(
                "Connectivity Monitor: event '%s' fired successfully", event_type
            )
        except (OSError, ValueError) as err:
            _LOGGER.error("Connectivity Monitor: failed to fire event: %s", str(err))

    async def _async_send_notification(self, service: str, message: str) -> None:
        """Send a notification."""
        try:
            # Add 'notify.' prefix if missing
            if not service.startswith("notify."):
                service = f"notify.{service}"

            _LOGGER.debug("Sending notification using service: %s", service)
            _LOGGER.debug("Notification message: %s", message)

            await self.hass.services.async_call(
                "notify",
                service.replace("notify.", ""),
                {"message": message},
                blocking=True,
            )
            _LOGGER.debug("Successfully sent notification")
        except (OSError, ValueError) as err:
            _LOGGER.error(
                "Failed to send notification using service %s: %s", service, str(err)
            )

    async def async_setup_alerts(self, entity_id: str, target: dict) -> None:
        """Set up alerts for a sensor."""
        alert_group = target.get(CONF_ALERT_GROUP)
        alert_action = target.get(CONF_ALERT_ACTION)

        if not alert_group and not alert_action:
            return

        action_delay = target.get(CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY)
        _LOGGER.info(
            "Connectivity Monitor: setting up alerts for %s — group=%s, action=%s, action_delay=%s min",
            entity_id,
            alert_group or "none",
            alert_action or "none",
            action_delay,
        )

        # Store target info for timer checks
        self._targets[entity_id] = target

        # Remove existing callback if any
        if entity_id in self._callbacks:
            self._callbacks[entity_id]()
            self._callbacks.pop(entity_id)

        async def async_handle_state_change(event) -> None:
            """Handle state changes for an entity."""
            # Handle both real events and our simulated initial state check
            if hasattr(event, "data"):
                new_state = event.data.get("new_state")
                old_state = event.data.get("old_state")
            else:
                new_state = event.get("new_state")
                old_state = event.get("old_state")

            if new_state is None:
                return

            current_time = datetime.now()
            is_zha = target.get(CONF_PROTOCOL) == PROTOCOL_ZHA
            is_inactive = target.get(CONF_PROTOCOL) in (
                PROTOCOL_ZHA,
                PROTOCOL_MATTER,
                PROTOCOL_ESPHOME,
                PROTOCOL_BLUETOOTH,
            )
            problem_states = (
                ["Inactive"]
                if is_inactive
                else ["Disconnected", "Not Connected", "Partially Connected"]
            )
            recovery_state = "Active" if is_inactive else "Connected"
            if target.get(CONF_PROTOCOL) == PROTOCOL_MATTER:
                identifier = target.get(CONF_MATTER_NODE_ID, target[CONF_HOST])
            elif target.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME:
                identifier = target.get(CONF_ESPHOME_DEVICE_ID, target[CONF_HOST])
            elif target.get(CONF_PROTOCOL) == PROTOCOL_BLUETOOTH:
                identifier = target.get(CONF_BLUETOOTH_ADDRESS, target[CONF_HOST])
            elif is_zha:
                identifier = target.get(CONF_ZHA_IEEE, target[CONF_HOST])
            else:
                identifier = target[CONF_HOST]
            device_name = target.get("device_name", identifier)

            # Device has entered a problem state
            if new_state.state in problem_states:
                # Cancel any in-progress recovery confirmation.
                self._recovering_since.pop(entity_id, None)
                # Only start timing if we weren't already in a problem state
                if entity_id not in self._last_disconnected or (
                    old_state and old_state.state not in problem_states
                ):
                    self._last_disconnected[entity_id] = current_time
                    self._notified[entity_id] = False
                    self._action_fired[entity_id] = False
                    _LOGGER.info(
                        "Connectivity Monitor: started tracking %s as %s since %s",
                        device_name,
                        new_state.state,
                        current_time.strftime("%H:%M:%S"),
                    )

            # Device has recovered
            elif new_state.state == recovery_state:
                if entity_id in self._last_disconnected:
                    # Start the recovery confirmation window.  The actual
                    # recovery processing (notifications, actions, cleanup) is
                    # handled by _check_alerts once the recovery has been
                    # stable for ≥ 60 s, so that brief false-positive "Connected"
                    # polls don't reset the alert delay countdown.
                    if entity_id not in self._recovering_since:
                        self._recovering_since[entity_id] = datetime.now()
                        _LOGGER.info(
                            "Connectivity Monitor: %s entered recovery state — confirming in 60s",
                            device_name,
                        )

        @callback
        def state_change_callback(event):
            """Callback wrapper for state change handler."""
            self.hass.async_create_task(async_handle_state_change(event))

        # Set up state tracking
        self._callbacks[entity_id] = async_track_state_change_event(
            self.hass, [entity_id], state_change_callback
        )

        # Check initial state
        state = self.hass.states.get(entity_id)
        if state and state.state != STATE_UNKNOWN:
            await async_handle_state_change({"new_state": state, "old_state": None})


class ConnectivityMonitorEntity(CoordinatorEntity["ConnectivityMonitorCoordinator"]):  # pylint: disable=hass-enforce-class-module
    """Shared entity helpers for target-backed sensors."""

    def __init__(
        self, coordinator: ConnectivityMonitorCoordinator, target: dict
    ) -> None:
        """Initialize the shared target-backed entity state."""
        super().__init__(coordinator)
        self.target = target

    @property
    def target_data(self) -> dict[str, Any]:
        """Return the last known payload for this entity's target."""
        return self.coordinator.get_target_data(self.target)

    def _target_data_for(self, target: dict) -> dict[str, Any]:
        """Return the last known payload for another target in the same entry."""
        return self.coordinator.get_target_data(target)


class ConnectivitySensor(ConnectivityMonitorEntity, SensorEntity):
    """Connectivity sensor for individual protocols."""

    def __init__(
        self, coordinator: ConnectivityMonitorCoordinator, target: dict
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, target)
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_name = target.get("device_name", target[CONF_HOST])
        safe_device_name = (
            device_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        )

        # Set up sensor name and ID based on protocol
        if target[CONF_PROTOCOL] == PROTOCOL_ICMP:
            self._attr_name = "ICMP (Ping)"
            entity_id_suffix = "icmp"
        elif target[CONF_PROTOCOL] == PROTOCOL_AD_DC:
            port_name = AD_DC_PORTS.get(target[CONF_PORT], str(target[CONF_PORT]))
            self._attr_name = f"AD {port_name}"
            entity_id_suffix = f"ad_{target[CONF_PORT]}"
        else:
            self._attr_name = f"{target[CONF_PROTOCOL]} {target[CONF_PORT]}"
            entity_id_suffix = f"{target[CONF_PROTOCOL].lower()}_{target[CONF_PORT]}"

        # Set entity ID
        self.entity_id = (
            f"sensor.connectivity_monitor_{safe_device_name}_{entity_id_suffix}"
        )

        # Get data from coordinator
        coord_data = coordinator.get_target_data(target)
        mac_address = coord_data.get("mac_address")
        ip_address = coord_data.get("resolved_ip")

        # Set unique_id with prefix
        base_id = None
        if mac_address:
            base_id = mac_address.lower().replace(":", "")
        elif ip_address:
            base_id = ip_address.replace(".", "_")
        else:
            base_id = target[CONF_HOST].replace(".", "_")

        self._attr_unique_id = f"connectivity_{base_id}_{target[CONF_PROTOCOL]}_{target.get(CONF_PORT, 'ping')}"

        # Set up device info
        connections = set()
        if mac_address:
            connections.add(("mac", mac_address.lower()))
        if ip_address:
            connections.add(("ip", ip_address))
        try:
            _parse_ip_address(target[CONF_HOST])
            connections.add(("ip", target[CONF_HOST]))
        except ValueError:
            connections.add(("hostname", target[CONF_HOST]))

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, mac_address.lower().replace(":", ""))
                if mac_address
                else (DOMAIN, target[CONF_HOST])
            },
            name=device_name,
            manufacturer="Connectivity Monitor",
            model="Network Monitor",
            hw_version=target[CONF_HOST],
            sw_version=VERSION,
            connections=connections,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self.target_data:
            return "Unknown"
        return (
            "Connected" if self.target_data.get("connected", False) else "Disconnected"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "host": self.target[CONF_HOST],
            "protocol": self.target[CONF_PROTOCOL],
        }

        if self.target[CONF_PROTOCOL] == PROTOCOL_AD_DC:
            attrs["port"] = self.target[CONF_PORT]
            attrs["service"] = AD_DC_PORTS.get(
                self.target[CONF_PORT], "Unknown Service"
            )
        elif self.target[CONF_PROTOCOL] != PROTOCOL_ICMP:
            attrs["port"] = self.target[CONF_PORT]

        if self.target_data:
            if self.target_data.get("latency") is not None:
                attrs["latency_ms"] = self.target_data["latency"]
            if self.target_data.get("resolved_ip"):
                attrs["resolved_ip"] = self.target_data["resolved_ip"]
            if self.target_data.get("mac_address"):
                attrs["mac_address"] = self.target_data["mac_address"]

        return attrs

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if not self.target_data or not self.target_data.get("connected", False):
            return "mdi:lan-disconnect"
        return "mdi:lan-connect"


class OverviewSensor(ConnectivityMonitorEntity, SensorEntity):
    """Overview sensor showing combined status."""

    def __init__(
        self,
        coordinator: ConnectivityMonitorCoordinator,
        target: dict,
        device_targets: list[dict],
    ) -> None:
        """Initialize the overview sensor."""
        super().__init__(coordinator, target)
        self._device_targets = device_targets
        self._alert_handler: AlertHandler | None = None
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_name = target.get("device_name", target[CONF_HOST])
        safe_device_name = (
            device_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        )

        self._attr_name = "Overall Status"
        self.entity_id = f"sensor.connectivity_monitor_{safe_device_name}_overall"

        # Get data from coordinator
        coord_data = coordinator.get_target_data(target)
        mac_address = coord_data.get("mac_address")
        ip_address = coord_data.get("resolved_ip")

        # Set unique_id with prefix
        if mac_address:
            base_id = mac_address.lower().replace(":", "")
        elif ip_address:
            base_id = ip_address.replace(".", "_")
        else:
            base_id = target[CONF_HOST].replace(".", "_")

        self._attr_unique_id = f"connectivity_{base_id}_overall"

        # Set up device info
        connections = set()
        if mac_address:
            connections.add(("mac", mac_address.lower()))
        if ip_address:
            connections.add(("ip", ip_address))
        try:
            _parse_ip_address(target[CONF_HOST])
            connections.add(("ip", target[CONF_HOST]))
        except ValueError:
            connections.add(("hostname", target[CONF_HOST]))

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, mac_address.lower().replace(":", ""))
                if mac_address
                else (DOMAIN, target[CONF_HOST])
            },
            name=device_name,
            manufacturer="Connectivity Monitor",
            model="Network Monitor",
            hw_version=target[CONF_HOST],
            sw_version=VERSION,
            connections=connections,
        )

    async def async_added_to_hass(self) -> None:
        """Set up alerts once the final entity_id is known."""
        await super().async_added_to_hass()
        alert_handler = getattr(self, "_alert_handler", None)
        if alert_handler and (
            self.target.get(CONF_ALERT_GROUP) or self.target.get(CONF_ALERT_ACTION)
        ):
            await alert_handler.async_setup_alerts(self.entity_id, self.target)

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self._device_targets:
            return "Unknown"

        all_connected = True
        any_connected = False

        for target in self._device_targets:
            target_data = self._target_data_for(target)
            if target_data.get("connected"):
                any_connected = True
            else:
                all_connected = False

        if all_connected:
            return "Connected"
        if any_connected:
            return "Partially Connected"
        return "Disconnected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "host": self.target[CONF_HOST],
            "device_name": self.target.get("device_name", self.target[CONF_HOST]),
            "monitored_services": [],
        }

        for target in self._device_targets:
            target_data = self._target_data_for(target)
            service = {
                "protocol": target[CONF_PROTOCOL],
                "status": "Connected"
                if target_data.get("connected")
                else "Disconnected",
            }

            if target[CONF_PROTOCOL] == PROTOCOL_AD_DC:
                service["port"] = target[CONF_PORT]
                service["service"] = AD_DC_PORTS.get(
                    target[CONF_PORT], "Unknown Service"
                )
            elif target[CONF_PROTOCOL] != PROTOCOL_ICMP:
                service["port"] = target[CONF_PORT]

            if target_data:
                if target_data.get("latency") is not None:
                    service["latency_ms"] = target_data["latency"]
                if target_data.get("mac_address"):
                    service["mac_address"] = target_data["mac_address"]

            attrs["monitored_services"].append(service)

        return attrs

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.native_value == "Connected":
            return "mdi:check-network"
        if self.native_value == "Partially Connected":
            return "mdi:network-strength-2"
        return "mdi:close-network"


class ADOverviewSensor(ConnectivityMonitorEntity, SensorEntity):
    """Overview sensor specifically for Active Directory status."""

    def __init__(
        self,
        coordinator: ConnectivityMonitorCoordinator,
        target: dict,
        ad_targets: list[dict],
    ) -> None:
        """Initialize the AD overview sensor."""
        super().__init__(coordinator, target)
        self._targets = ad_targets
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_name = target.get("device_name", target[CONF_HOST])
        safe_device_name = (
            device_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        )

        self._attr_name = "Active Directory"
        self.entity_id = f"sensor.connectivity_monitor_{safe_device_name}_ad"

        # Get data from coordinator
        coord_data = coordinator.get_target_data(target)
        mac_address = coord_data.get("mac_address")
        ip_address = coord_data.get("resolved_ip")

        # Set unique_id with prefix
        base_id = None
        if mac_address:
            base_id = mac_address.lower().replace(":", "")
        elif ip_address:
            base_id = ip_address.replace(".", "_")
        else:
            base_id = target[CONF_HOST].replace(".", "_")

        self._attr_unique_id = f"connectivity_{base_id}_ad"

        # Set up device info
        connections = set()
        if mac_address:
            connections.add(("mac", mac_address.lower()))
        if ip_address:
            connections.add(("ip", ip_address))
        try:
            _parse_ip_address(target[CONF_HOST])
            connections.add(("ip", target[CONF_HOST]))
        except ValueError:
            connections.add(("hostname", target[CONF_HOST]))

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, mac_address.lower().replace(":", ""))
                if mac_address
                else (DOMAIN, target[CONF_HOST])
            },
            name=device_name,
            manufacturer="Connectivity Monitor",
            model="Network Monitor",
            hw_version=target[CONF_HOST],
            sw_version=VERSION,
            connections=connections,
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self._targets:
            return "Not Connected"

        all_connected = True
        any_connected = False

        for target in self._targets:
            target_data = self._target_data_for(target)
            if target_data.get("connected"):
                any_connected = True
            else:
                all_connected = False

        if all_connected:
            return "Connected"
        if any_connected:
            return "Partially Connected"
        return "Not Connected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "host": self.target[CONF_HOST],
            "device_name": self.target.get("device_name", self.target[CONF_HOST]),
            "ad_services": [],
        }

        for target in self._targets:
            target_data = self._target_data_for(target)
            service = {
                "port": target[CONF_PORT],
                "service": AD_DC_PORTS.get(target[CONF_PORT], "Unknown Service"),
                "status": "Connected"
                if target_data.get("connected")
                else "Not Connected",
            }

            if target_data.get("latency") is not None:
                service["latency_ms"] = target_data["latency"]

            attrs["ad_services"].append(service)

        return attrs

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.native_value == "Connected":
            return "mdi:domain"
        if self.native_value == "Partially Connected":
            return "mdi:domain-remove"
        return "mdi:domain-off"


class ZHASensor(ConnectivityMonitorEntity, SensorEntity):
    """Sensor for a ZHA (ZigBee) device activity status based on last_seen."""

    def __init__(
        self, coordinator: ConnectivityMonitorCoordinator, target: dict
    ) -> None:
        """Initialize the ZHA sensor."""
        super().__init__(coordinator, target)
        self._alert_handler: AlertHandler | None = None
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_name = target.get("device_name", target[CONF_ZHA_IEEE])
        safe_name = (
            device_name.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "_")
            .replace(":", "_")
        )

        self._attr_name = "ZigBee Status"
        self.entity_id = f"sensor.connectivity_monitor_zha_{safe_name}"

        # Unique ID scoped to this integration
        ieee_clean = target[CONF_ZHA_IEEE].replace(":", "").replace("-", "")
        self._attr_unique_id = f"connectivity_zha_{ieee_clean}"

        # Merge onto the existing ZHA device by using ZHA's own identifier.
        # This places the sensor alongside the device's entities in HA rather
        # than creating a separate device, and EntityCategory.DIAGNOSTIC puts
        # it in a distinct "Diagnostics" card on the device page.
        self._attr_device_info = DeviceInfo(
            identifiers={("zha", target[CONF_ZHA_IEEE])},
        )

    @property
    def native_value(self) -> str:
        """Return Active / Inactive / Unknown."""
        if not self.target_data:
            return "Unknown"
        return "Active" if self.target_data.get("active") else "Inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes used by the panel."""
        ieee = self.target[CONF_ZHA_IEEE]
        timeout = self.target.get(CONF_INACTIVE_TIMEOUT, DEFAULT_INACTIVE_TIMEOUT)
        attrs = {
            "ieee": ieee,
            "device_name": self.target.get("device_name", ieee),
            "timeout_minutes": timeout,
            "monitor_type": "zha",
        }
        if self.target.get(CONF_ALERT_GROUP):
            attrs["alert_group"] = self.target[CONF_ALERT_GROUP]
            attrs["alert_delay"] = self.target.get(
                CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY
            )
        if self.target.get(CONF_ALERT_ACTION):
            attrs["alert_action"] = self.target[CONF_ALERT_ACTION]
            attrs["alert_action_delay"] = self.target.get(
                CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
            )
        if self.target_data:
            raw_ts = self.target_data.get("last_seen")
            if raw_ts is not None:
                attrs["last_seen"] = datetime.fromtimestamp(raw_ts).isoformat()
            minutes_ago = self.target_data.get("minutes_ago")
            if minutes_ago is not None:
                attrs["minutes_ago"] = minutes_ago
        return attrs

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.target_data and self.target_data.get("active"):
            return "mdi:zigbee"
        return "mdi:lan-disconnect"

    async def async_added_to_hass(self) -> None:
        """Set up alerts after entity_id is finalised by HA registry."""
        await super().async_added_to_hass()
        alert_handler = getattr(self, "_alert_handler", None)
        if alert_handler and (
            self.target.get(CONF_ALERT_GROUP) or self.target.get(CONF_ALERT_ACTION)
        ):
            await alert_handler.async_setup_alerts(self.entity_id, self.target)


class MatterSensor(ConnectivityMonitorEntity, SensorEntity):
    """Sensor for a Matter device activity status based on entity availability."""

    def __init__(
        self, coordinator: ConnectivityMonitorCoordinator, target: dict
    ) -> None:
        """Initialize the Matter sensor."""
        super().__init__(coordinator, target)
        self._alert_handler: AlertHandler | None = None
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_name = target.get("device_name", target[CONF_MATTER_NODE_ID])
        safe_name = (
            device_name.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "_")
            .replace(":", "_")
        )

        self._attr_name = "Matter Status"
        self.entity_id = f"sensor.connectivity_monitor_matter_{safe_name}"

        # Unique ID scoped to this integration
        node_id_clean = target[CONF_MATTER_NODE_ID].replace("-", "_").replace(":", "_")
        self._attr_unique_id = f"connectivity_matter_{node_id_clean}"

        # Merge onto the existing Matter device by using the Matter domain identifier.
        # EntityCategory.DIAGNOSTIC places it in the Diagnostics card on the device page.
        self._attr_device_info = DeviceInfo(
            identifiers={("matter", target[CONF_MATTER_NODE_ID])},
        )

    @property
    def native_value(self) -> str:
        """Return Active / Inactive / Unknown."""
        if not self.target_data:
            return "Unknown"
        if not self.target_data.get("device_found"):
            return "Unknown"
        return "Active" if self.target_data.get("active") else "Inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes used by the panel."""
        node_id = self.target[CONF_MATTER_NODE_ID]
        attrs = {
            "node_id": node_id,
            "device_name": self.target.get("device_name", node_id),
            "monitor_type": "matter",
        }
        if self.target.get(CONF_ALERT_GROUP):
            attrs["alert_group"] = self.target[CONF_ALERT_GROUP]
            attrs["alert_delay"] = self.target.get(
                CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY
            )
        if self.target.get(CONF_ALERT_ACTION):
            attrs["alert_action"] = self.target[CONF_ALERT_ACTION]
            attrs["alert_action_delay"] = self.target.get(
                CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
            )
        return attrs

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.target_data and self.target_data.get("active"):
            return "mdi:chip"
        return "mdi:lan-disconnect"

    async def async_added_to_hass(self) -> None:
        """Set up alerts after entity_id is finalised by HA registry."""
        await super().async_added_to_hass()
        alert_handler = getattr(self, "_alert_handler", None)
        if alert_handler and (
            self.target.get(CONF_ALERT_GROUP) or self.target.get(CONF_ALERT_ACTION)
        ):
            await alert_handler.async_setup_alerts(self.entity_id, self.target)


class ESPHomeSensor(ConnectivityMonitorEntity, SensorEntity):
    """Sensor for an ESPHome device activity status based on entity availability."""

    def __init__(
        self, coordinator: ConnectivityMonitorCoordinator, target: dict
    ) -> None:
        """Initialize the ESPHome sensor."""
        super().__init__(coordinator, target)
        self._alert_handler: AlertHandler | None = None
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_name = target.get("device_name", target[CONF_ESPHOME_DEVICE_ID])
        safe_name = (
            device_name.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "_")
            .replace(":", "_")
        )

        self._attr_name = "ESPHome Status"
        self.entity_id = f"sensor.connectivity_monitor_esphome_{safe_name}"

        # Unique ID scoped to this integration
        device_id_clean = (
            target[CONF_ESPHOME_DEVICE_ID].replace("-", "_").replace(":", "_")
        )
        self._attr_unique_id = f"connectivity_esphome_{device_id_clean}"

        # Merge onto the existing ESPHome device so the sensor appears on the
        # device page alongside the device's own entities.
        #
        # Strategy (most → least reliable):
        #   1. MAC via connections — ESPHome always sets this; HA uses it for
        #      device lookup before checking identifiers.
        #   2. esphome_identifier — the ("esphome", <value>) identifier stored
        #      at config time.
        #   3. entry_id fallback — last resort; may create a new unnamed device
        #      if neither of the above is present (only for old config entries).
        mac_address = target.get("esphome_mac")
        esphome_identifier = (
            target.get("esphome_identifier") or target[CONF_ESPHOME_DEVICE_ID]
        )

        device_info_kwargs: dict = {
            "identifiers": {("esphome", esphome_identifier)},
        }
        if mac_address:
            device_info_kwargs["connections"] = {(CONNECTION_NETWORK_MAC, mac_address)}

        self._attr_device_info = DeviceInfo(**device_info_kwargs)

    @property
    def native_value(self) -> str:
        """Return Active / Inactive / Unknown."""
        if not self.target_data:
            return "Unknown"
        if not self.target_data.get("device_found"):
            return "Unknown"
        return "Active" if self.target_data.get("active") else "Inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes used by the panel."""
        device_id = self.target[CONF_ESPHOME_DEVICE_ID]
        attrs = {
            "device_id": device_id,
            "device_name": self.target.get("device_name", device_id),
            "monitor_type": "esphome",
        }
        if self.target.get(CONF_ALERT_GROUP):
            attrs["alert_group"] = self.target[CONF_ALERT_GROUP]
            attrs["alert_delay"] = self.target.get(
                CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY
            )
        if self.target.get(CONF_ALERT_ACTION):
            attrs["alert_action"] = self.target[CONF_ALERT_ACTION]
            attrs["alert_action_delay"] = self.target.get(
                CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
            )
        return attrs

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.target_data and self.target_data.get("active"):
            return "mdi:chip"
        return "mdi:lan-disconnect"

    async def async_added_to_hass(self) -> None:
        """Set up alerts after entity_id is finalised by HA registry."""
        await super().async_added_to_hass()
        alert_handler = getattr(self, "_alert_handler", None)
        if alert_handler and (
            self.target.get(CONF_ALERT_GROUP) or self.target.get(CONF_ALERT_ACTION)
        ):
            await alert_handler.async_setup_alerts(self.entity_id, self.target)


class BluetoothSensor(ConnectivityMonitorEntity, SensorEntity):
    """Sensor for a Bluetooth device activity status based on entity availability."""

    def __init__(
        self, coordinator: ConnectivityMonitorCoordinator, target: dict
    ) -> None:
        """Initialize the Bluetooth sensor."""
        super().__init__(coordinator, target)
        self._alert_handler: AlertHandler | None = None
        self._attr_has_entity_name = True
        self._attr_available = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        device_name = target.get("device_name", target[CONF_BLUETOOTH_ADDRESS])
        safe_name = (
            device_name.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "_")
            .replace(":", "_")
        )

        self._attr_name = "Bluetooth Status"
        self.entity_id = f"sensor.connectivity_monitor_bluetooth_{safe_name}"

        bt_address_clean = (
            target[CONF_BLUETOOTH_ADDRESS].replace("-", "_").replace(":", "_")
        )
        self._attr_unique_id = f"connectivity_bluetooth_{bt_address_clean}"

        self._attr_device_info = DeviceInfo(
            identifiers={("bluetooth", target[CONF_BLUETOOTH_ADDRESS])},
        )

    @property
    def native_value(self) -> str:
        """Return Active / Inactive / Unknown."""
        if not self.target_data:
            return "Unknown"
        if not self.target_data.get("device_found"):
            return "Unknown"
        return "Active" if self.target_data.get("active") else "Inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes used by the panel."""
        bt_address = self.target[CONF_BLUETOOTH_ADDRESS]
        attrs = {
            "bt_address": bt_address,
            "device_name": self.target.get("device_name", bt_address),
            "monitor_type": "bluetooth",
        }
        if self.target_data:
            if self.target_data.get("rssi") is not None:
                attrs["rssi"] = self.target_data["rssi"]
            if self.target_data.get("source"):
                attrs["source"] = self.target_data["source"]
            if self.target_data.get("connectable") is not None:
                attrs["connectable"] = self.target_data["connectable"]
            if self.target_data.get("service_uuids"):
                attrs["service_uuids"] = self.target_data["service_uuids"]
            if self.target_data.get("manufacturer_data"):
                attrs["manufacturer_data"] = self.target_data["manufacturer_data"]
            if self.target_data.get("service_data"):
                attrs["service_data"] = self.target_data["service_data"]
            if self.target_data.get("time") is not None:
                attrs["last_seen_time"] = self.target_data["time"]
            if self.target_data.get("tx_power") is not None:
                attrs["tx_power"] = self.target_data["tx_power"]
        if self.target.get(CONF_ALERT_GROUP):
            attrs["alert_group"] = self.target[CONF_ALERT_GROUP]
            attrs["alert_delay"] = self.target.get(
                CONF_ALERT_DELAY, DEFAULT_ALERT_DELAY
            )
        if self.target.get(CONF_ALERT_ACTION):
            attrs["alert_action"] = self.target[CONF_ALERT_ACTION]
            attrs["alert_action_delay"] = self.target.get(
                CONF_ALERT_ACTION_DELAY, DEFAULT_ALERT_ACTION_DELAY
            )
        return attrs

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.target_data and self.target_data.get("active"):
            return "mdi:bluetooth"
        return "mdi:bluetooth-off"

    async def async_added_to_hass(self) -> None:
        """Set up alerts after entity_id is finalised by HA registry."""
        await super().async_added_to_hass()
        alert_handler = getattr(self, "_alert_handler", None)
        if alert_handler and (
            self.target.get(CONF_ALERT_GROUP) or self.target.get(CONF_ALERT_ACTION)
        ):
            await alert_handler.async_setup_alerts(self.entity_id, self.target)
