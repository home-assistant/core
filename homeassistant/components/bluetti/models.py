"""Domain models for the BLUETTI integration's cloud-sourced devices and state."""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, override

from pybluetti import ProductClient, UnifyResponse, UserProduct

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import BluettiDeviceCoordinator  # pragma: no cover

__LOGGER__ = logging.getLogger(__name__)

manufacturer = "Bluetti"


class BluettiData:
    """Data for the BLUETTI integration."""

    def __init__(
        self, hass: HomeAssistant, devices: list[UserProduct] | None = None
    ) -> None:
        """Build the device list from the cloud account's bound products."""
        self.devices = [
            BluettiDevice(
                device_id=dev.sn,
                on_line=dev.online or "0",
                # Falls back to the serial only when the cloud doesn't
                # report a name at all - dev.name is `str | None` on the
                # wire, and the serial is the only thing guaranteed present.
                name=dev.name or dev.sn,
                sn=dev.sn,
                model=dev.model or "Unknown",
                state_list=dev.stateList or [],
            )
            for dev in devices or []
        ]
        self.loop = hass.loop

    async def test_connection(self) -> bool:
        """Test connectivity to devices."""
        await asyncio.sleep(0.1)
        return True

    def get_device_by_sn(self, sn: str) -> BluettiDevice | None:
        """Return the device with this serial number, if it's tracked here."""
        for dev in self.devices:
            if dev.device_id == sn:
                return dev
        return None

    def web_socket_message_handler(self, message: str) -> None:
        """Handle an incoming STOMP websocket message by refreshing its device."""
        __LOGGER__.debug("Received BLUETTI websocket message: %s", message)

        res = json.loads(message)
        sn = res["data"]["deviceSn"]

        device = self.get_device_by_sn(sn)
        if device and device.coordinator:
            # This runs on the websocket thread, not the event loop, so a
            # thread-safe scheduling call is required here.
            asyncio.run_coroutine_threadsafe(
                device.coordinator.async_request_refresh(), self.loop
            )


class BluettiState:
    """Represents a single function/state of the device."""

    def __init__(
        self,
        fn_code: str,
        fn_name: str,
        fn_value: str,
        fn_type: str,
        support_mode_values: list[dict[str, Any]] | None = None,
        sensor_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the state from one entry of the cloud's stateList."""
        self.fn_code = fn_code
        self.fn_name = fn_name
        self.fn_value = fn_value
        self.fn_type = fn_type
        self.support_mode_values = support_mode_values or []
        self.sensor_info = sensor_info or {}

    def is_switch(self) -> bool:
        """Return whether this state is a plain on/off switch."""
        return len(self.support_mode_values) == 0

    def set_value(self, value: str) -> None:
        """Set the state value, validate if mode selection."""
        if self.is_switch() or any(
            v["code"] == value for v in self.support_mode_values
        ):
            self.fn_value = value
        else:
            raise ValueError(f"Invalid value {value} for {self.fn_code}")

    def get_name_for_value(self) -> str:
        """Return human-readable name for current value."""
        if self.is_switch():
            return "On" if self.fn_value == "1" else "Off"
        for v in self.support_mode_values:
            if v["code"] == self.fn_value:
                return str(v["name"])
        return self.fn_value

    @override
    def __repr__(self) -> str:
        """Return a debug representation showing the state's code and value."""
        return f"<BluettiState {self.fn_code}={self.fn_value}>"


class BluettiDevice:
    """Represents a single Bluetti device."""

    def __init__(
        self,
        device_id: str,
        on_line: str,
        name: str,
        sn: str,
        model: str,
        state_list: list[dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the device from the cloud's product/state data."""
        self.device_id = device_id
        self.on_line = on_line
        self.name = name
        self.sn = sn
        self.model = model
        self.manufacturer = manufacturer
        self.coordinator: BluettiDeviceCoordinator | None = None
        self.states = [
            BluettiState(
                fn_code=s.get("fnCode") or "",
                # fnName is sometimes empty on the wire - fall back to
                # fn_code so entities never get a blank display name.
                fn_name=s.get("fnName") or s.get("fnCode") or "",
                fn_value=s.get("fnValue") or "",
                fn_type=s.get("fnType") or "",
                support_mode_values=s.get("supportModeValues"),
                sensor_info=s.get("sensorInfo"),
            )
            for s in state_list or []
        ]

        self._api_client: ProductClient | None = None
        self._unbind_processed = False
        self._hass: HomeAssistant | None = None
        self._entry: ConfigEntry | None = None
        self._entry_id: str | None = None

    def bind_runtime(
        self, api_client: ProductClient, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Attach the runtime dependencies this device needs once the entry is set up.

        These aren't constructor parameters because BluettiData builds every
        device from the cloud's product list before api_client/hass/entry
        exist in async_setup_entry's scope - see __init__.py's coordinator
        setup loop, which calls this right after construction.
        """
        self._api_client = api_client
        self._hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id

    @override
    def __repr__(self) -> str:
        """Return a debug representation showing the device's id and name."""
        return f"<BluettiDevice id={self.device_id} name={self.name}>"

    def get_state(self, fn_code: str) -> BluettiState | None:
        """Return state object by fn_code."""
        for s in self.states:
            if s.fn_code == fn_code:
                return s
        return None

    async def set_state_value(self, fn_code: str, value: str) -> None:
        """Send a control command to the device and notify the coordinator."""
        state = self.get_state(fn_code)
        if not state:
            raise ValueError(f"No state with code {fn_code}")

        assert self._api_client is not None, (
            "set_state_value called before the device was wired up"
        )
        try:
            result = await self._api_client.control_device(
                {"sn": self.device_id, "fnCode": fn_code, "fnValue": value}
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "device_id": self.device_id,
                    "error": str(err),
                },
            ) from err

        # control_device() doesn't raise on a rejected command - check
        # msgCode. Tracked upstream: bluetti-community/pybluetti#1.
        if not (isinstance(result, UnifyResponse) and result.msgCode == 0):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={
                    "device_id": self.device_id,
                    "error": str(result),
                },
            )
        state.set_value(value)

        if self.coordinator:
            self.coordinator.async_set_updated_data(self)

    # online/battery_level derive from stateList, which pybluetti.UserProduct
    # exposes untyped - candidates to move into the library eventually, but
    # entangled with this class's own state parsing. Tracked upstream:
    # bluetti-community/pybluetti#1.
    @property
    def online(self) -> bool:
        """Return whether the cloud reports this device as online."""
        return self.on_line == "1"

    @property
    def battery_level(self) -> int:
        """Return the device's state of charge, or 0 if not reported."""
        state = self.get_state("SOC")
        if state:
            return int(state.fn_value)
        return 0

    async def async_refresh_from_api(self) -> None:
        """Fetch the latest state from the BLUETTI cloud API and apply it.

        Raises on any failure so the coordinator can classify and surface it.
        """
        assert self._api_client is not None, (
            "async_refresh_from_api called before the device was wired up"
        )
        device_status = await self._api_client.get_device_status(self.device_id)
        if not device_status.data:
            raise RuntimeError(f"Empty status response for device {self.device_id}")
        data = device_status.data[0]

        if data.sn != self.device_id:
            return

        if data.isBindByCurUser == "0" and not self._unbind_processed:
            await self._handle_unbind()
            return

        self.on_line = data.online

        for s in data.stateList:
            state_obj = self.get_state(s["fnCode"])
            if state_obj:
                state_obj.fn_value = s["fnValue"]

    async def _handle_unbind(self) -> None:
        """Handle device unbinding: clean up the device, entity, and configuration, and display the notification.

        Each cleanup step below is wrapped in its own broad except: a failure
        in one (e.g. deleting one stale entity) must not prevent the later
        steps (updating the config entry, notifying the user) from running.
        """
        __LOGGER__.info("Detected device unbinding: %s (%s)", self.name, self.device_id)

        # Not marking _unbind_processed here - a retriable setup-ordering
        # issue (unbind detected before bind_runtime() ran), not terminal.
        if not self._hass or not self._entry:
            __LOGGER__.error(
                "Cannot handle device unbinding: missing necessary references "
                "(hass=%s, entry=%s)",
                self._hass is not None,
                self._entry is not None,
            )
            return

        # Set once cleanup is actually about to run - each step below is
        # independently best-effort (see the docstring).
        self._unbind_processed = True

        hass = self._hass
        entry = self._entry
        entry_id = self._entry_id or entry.entry_id

        try:
            __LOGGER__.info("Start handling device unbinding: %s", self.device_id)

            # 1. Get the device registry and entity registry
            device_registry = dr.async_get(hass)
            entity_registry = er.async_get(hass)

            # 2. Find and delete all entities of the device
            device_entry = None
            for dev_entry in dr.async_entries_for_config_entry(
                device_registry, entry_id
            ):
                if (DOMAIN, self.device_id) in dev_entry.identifiers:
                    device_entry = dev_entry
                    break

            if device_entry:
                # Delete all entities of the device
                entities_to_remove = [
                    entity_entry.entity_id
                    for entity_entry in er.async_entries_for_config_entry(
                        entity_registry, entry_id
                    )
                    if entity_entry.device_id == device_entry.id
                ]

                for entity_id in entities_to_remove:
                    try:
                        entity_registry.async_remove(entity_id)
                        __LOGGER__.debug("Deleted entity: %s", entity_id)
                    except Exception as e:  # noqa: BLE001 - one entity's removal must not block the rest
                        __LOGGER__.warning("Error deleting entity %s: %s", entity_id, e)

                # 3. Delete the device registry
                try:
                    device_registry.async_remove_device(device_entry.id)
                    __LOGGER__.debug("Deleted device registry: %s", device_entry.id)
                except Exception as e:  # noqa: BLE001 - best-effort cleanup step, see the method docstring
                    __LOGGER__.warning("Error deleting device registry: %s", e)
            else:
                __LOGGER__.warning("Device registry not found: %s", self.device_id)

            # 4. Remove the device (and its coordinators) from the runtime data
            try:
                runtime_data = getattr(entry, "runtime_data", None)
                if runtime_data:
                    runtime_data.bluetti_devices.devices = [
                        d
                        for d in runtime_data.bluetti_devices.devices
                        if d.device_id != self.device_id
                    ]
                    coordinator = runtime_data.coordinators.pop(self.device_id, None)
                    if coordinator:
                        await coordinator.async_shutdown()
                    __LOGGER__.debug(
                        "Removed device from runtime data: %s", self.device_id
                    )
            except Exception as e:  # noqa: BLE001 - best-effort cleanup step, see the method docstring
                __LOGGER__.warning("Error removing device from runtime data: %s", e)

            # 5. Remove the device from the configuration entry
            try:
                current_options = dict(entry.options)
                current_devices = current_options.get("devices", [])

                # Also drop the cached product entry - a re-bind would
                # otherwise reuse this stale name/model instead of fetching
                # fresh data.
                current_products = entry.data.get("products", [])
                new_products = [
                    p
                    for p in current_products
                    if (p.get("sn") if isinstance(p, dict) else p.sn) != self.device_id
                ]

                if self.device_id in current_devices:
                    new_devices = [d for d in current_devices if d != self.device_id]

                    # One call for both data and options - two separate
                    # calls would fire the entry's update listener twice.
                    hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, "products": new_products},
                        options={**current_options, "devices": new_devices},
                    )
                    __LOGGER__.debug(
                        "Removed device from configuration entry: %s", self.device_id
                    )
                else:
                    __LOGGER__.warning(
                        "Device %s not in the device list of the configuration entry",
                        self.device_id,
                    )
                    if new_products != current_products:
                        hass.config_entries.async_update_entry(
                            entry, data={**entry.data, "products": new_products}
                        )
            except Exception as e:  # noqa: BLE001 - best-effort cleanup step, see the method docstring
                __LOGGER__.error(
                    "Error updating configuration entry: %s", e, exc_info=True
                )
                # Even if the update fails, continue to display the notification

            # 6. Display persistent notification
            try:
                notification_id = f"bluetti_unbind_{self.device_id}"
                notification_title = "BLUETTI device has been unbound"
                notification_message = (
                    f"Device **{self.name}** ({self.device_id}) has been unbound in the cloud, "
                    f"and has been automatically removed from the Home Assistant integration.\n\n"
                    f"If this is a mistake, please re-add the device."
                )

                persistent_notification.async_create(
                    hass,
                    title=notification_title,
                    message=notification_message,
                    notification_id=notification_id,
                )
                __LOGGER__.debug("Displayed unbinding notification: %s", self.device_id)
            except Exception as e:  # noqa: BLE001 - best-effort cleanup step, see the method docstring
                __LOGGER__.warning("Error displaying notification: %s", e)

            # No explicit reload here - step 5's options update already
            # fires the entry's update listener; an extra explicit reload
            # used to double it.
            __LOGGER__.info("Device unbinding processing completed: %s", self.device_id)

        except Exception as e:  # noqa: BLE001 - outermost guard: never let unbind handling crash the caller
            __LOGGER__.error("Error handling device unbinding: %s", e, exc_info=True)
