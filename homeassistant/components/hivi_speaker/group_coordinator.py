"""Group coordinator for HiVi Speaker multi-room sync."""

import asyncio
import binascii
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional, Set
import logging
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .device import HIVIDevice
from hivico import HivicoClient

_LOGGER = logging.getLogger(__name__)

# Callback invoked with a single result dict; must be async (awaitable).
OperationResultCallback = Optional[Callable[[Dict[str, Any]], Awaitable[None]]]


class HIVIGroupCoordinator:
    """Group operation coordinator, handles master-slave setup status synchronization (improved version)"""

    def __init__(self, hass, device_manager, discovery_scheduler):
        self.hass = hass
        self.device_manager = device_manager
        self.discovery_scheduler = discovery_scheduler

        # Operation tracking
        self._pending_operations: Dict[str, Dict] = {}  # operation_id -> operation_data
        self._operation_timeout = 30  # Operation timeout (seconds)
        self._poll_interval = 2  # Polling interval (seconds)
        self._max_retries = 15  # Maximum retry count (30 seconds/2 seconds)

        # Polling tasks
        self._poll_tasks: Dict[str, asyncio.Task] = {}  # operation_id -> polling task
        self._coordinator_running = False

        # Add lock and callback tracking
        self._operation_lock = asyncio.Lock()
        self._request_callbacks: Dict[str, Callable] = {}  # operation_id -> callback

        # Store cancellation functions
        self._dispatcher_connections = []
        self._unsub_operation_started = None
        self._unsub_device_updated = None

    async def async_start(self):
        """Start coordinator"""
        self._coordinator_running = True

        # Listen for operation events
        self._unsub_operation_started = self.hass.bus.async_listen(
            f"{DOMAIN}_group_operation_started", self._handle_operation_started
        )

        # Listen for device status changes
        self._unsub_device_updated = self.hass.bus.async_listen(
            f"{DOMAIN}_device_updated", self._handle_device_updated
        )

        @callback
        def _handle_sync_group_operation(operation_data: Dict, callback_func: Callable):
            """Handle discovery signal"""
            _LOGGER.debug("Received sync group operation request: %s", operation_data)
            asyncio.create_task(
                self.async_set_slave_speaker(operation_data, callback_func)
            )

        # Register signal handler (supports parameterized callbacks)
        cancel_func = async_dispatcher_connect(
            self.hass, f"{DOMAIN}_sync_group_operation", _handle_sync_group_operation
        )
        self._dispatcher_connections.append(cancel_func)

    async def async_stop(self):
        """Stop coordinator"""
        self._coordinator_running = False

        # Cancel all polling tasks
        for operation_id, task in list(self._poll_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._poll_tasks.clear()
        self._pending_operations.clear()

        # Cancel bus listeners
        if self._unsub_operation_started is not None:
            self._unsub_operation_started()
            self._unsub_operation_started = None
        if self._unsub_device_updated is not None:
            self._unsub_device_updated()
            self._unsub_device_updated = None

        # Cancel all dispatcher signal listeners
        for cancel_func in self._dispatcher_connections:
            cancel_func()
        self._dispatcher_connections.clear()

        _LOGGER.debug("group coordinator stopped")

    async def async_set_slave_speaker(
        self,
        operation_data: Dict,
        callback_func: OperationResultCallback = None,
    ) -> Dict[str, Any]:
        """Set slave speaker (with full callback support)"""

        # Use new request handling mechanism
        result = await self.async_handle_discovery_request(
            operation_data, callback_func
        )

        if not result.get("accepted", False):
            return result

        operation_id = result["operation_id"]

        # Start processing task (includes polling)
        asyncio.create_task(self.async_start_operation_processing(operation_id))

        return result

    async def async_remove_slave_speaker(
        self,
        master_speaker_device_id: str,
        slave_speaker_device_id: str,
        callback_func: OperationResultCallback = None,
    ) -> Dict[str, Any]:
        """Remove slave speaker (with full callback support)"""
        operation_data = {
            "type": "remove_slave",
            "master": master_speaker_device_id,
            "slave": slave_speaker_device_id,
            "expected_state": "standalone",
        }

        # Use new request handling mechanism
        result = await self.async_handle_discovery_request(
            operation_data, callback_func
        )

        if not result.get("accepted", False):
            return result

        operation_id = result["operation_id"]

        # Start processing task (includes polling)
        asyncio.create_task(self.async_start_operation_processing(operation_id))

        return result

    async def async_handle_discovery_request(
        self,
        operation_data: Dict,
        callback_func: OperationResultCallback = None,
    ) -> Dict[str, Any]:
        """Handle discovery request, return result via callback_func"""
        operation_id = self._generate_operation_id(operation_data)

        async with self._operation_lock:
            # Check if same operation already in progress
            if operation_id in self._pending_operations:
                operation = self._pending_operations[operation_id]
                result = {
                    "status": "rejected",
                    "operation_id": operation_id,
                    "extra": {
                        "reason": "operation_already_exists",
                        "existing_status": operation.get("status", "unknown"),
                    },
                }

                if callback_func:
                    await callback_func(result)
                return result

            # Check for conflicting operations
            conflict_info = self._check_conflicting_operations(operation_data)
            if conflict_info["has_conflict"]:
                result = {
                    "status": "rejected",
                    "operation_id": operation_id,
                    "extra": {
                        "reason": "conflicting_operation",
                        "conflicting_operation": conflict_info["conflicting_operation"],
                    },
                }

                if callback_func:
                    await callback_func(result)
                return result

            # Accept new operation
            self._pending_operations[operation_id] = {
                "type": operation_data.get("type"),
                "master": operation_data.get("master"),
                "slave": operation_data.get("slave"),
                "start_time": datetime.now(),
                "expected_state": operation_data.get("expected_state"),
                "retry_count": 0,
                "last_check": None,
                "status": "pending",
                "data": operation_data,
                "request_callback": callback_func,  # Save callback function
            }

            # Save callback for subsequent notifications
            if callback_func:
                self._request_callbacks[operation_id] = callback_func

            result = {
                "accepted": True,
                "operation_id": operation_id,
                "reason": "accepted",
            }

            # Immediately return acceptance result via callback_func
            if callback_func:
                await callback_func(
                    {
                        "status": "accepted",
                        "operation_id": operation_id,
                        "extra": {
                            "timestamp": datetime.now().isoformat(),
                        },
                    },
                )

            # _LOGGER.info("Discovery request accepted: %s", operation_id)
            return result

    def _generate_operation_id(self, operation_data: Dict) -> str:
        """Generate unique operation ID"""
        op_type = operation_data.get("type", "unknown")
        master = operation_data.get("master", "unknown")
        slave = operation_data.get("slave", "unknown")
        return f"{op_type}_master_{master}_slave_{slave}"

    def _check_conflicting_operations(self, new_operation: Dict) -> Dict[str, Any]:
        """Check for conflicting operations

        Conflict rules:
        1. If new operation's master is an existing operation's slave → conflict
        2. If new operation's slave is a master or slave in any existing operation → conflict

        Args:
            new_operation: New operation data, contains master and slave device IDs

        Returns:
            Dict: Conflict check result
        """
        # Extract device IDs from new operation
        new_master = new_operation.get("master")
        new_slave = new_operation.get("slave")
        new_type = new_operation.get("type")

        _LOGGER.debug(
            "Start checking operation conflicts - New operation: type=%s, master=%s, slave=%s",
            new_type,
            new_master,
            new_slave,
        )
        _LOGGER.debug(
            "Current pending operations count: %d", len(self._pending_operations)
        )

        # If no pending operations, return no conflict
        if not self._pending_operations:
            _LOGGER.debug("No pending operations, new operation has no conflict")
            return {
                "has_conflict": False,
                "conflicting_operation": None,
                "conflict_type": "no_conflict",
                "conflict_reason": "No pending operations",
            }

        # Collect device usage from all existing operations
        existing_masters = set()
        existing_slaves = set()
        all_used_devices = set()

        for op_id, operation in self._pending_operations.items():
            existing_master = operation.get("master")
            existing_slave = operation.get("slave")

            if existing_master:
                existing_masters.add(existing_master)
                all_used_devices.add(existing_master)
            if existing_slave:
                existing_slaves.add(existing_slave)
                all_used_devices.add(existing_slave)

            _LOGGER.debug(
                "Existing operation: id=%s, master=%s, slave=%s, status=%s",
                op_id,
                existing_master,
                existing_slave,
                operation.get("status", "unknown"),
            )

        _LOGGER.debug(
            "Device usage statistics - Existing master devices: %s, Existing slave devices: %s, All used devices: %s",
            existing_masters,
            existing_slaves,
            all_used_devices,
        )

        # Rule 1: Check if new master is a slave in existing operations
        if new_master and new_master in existing_slaves:
            conflict_op = self._find_operation_by_slave(new_master)
            _LOGGER.warning(
                "Conflict! New operation's master device %s is a slave in existing operation",
                new_master,
            )
            return {
                "has_conflict": True,
                "conflicting_operation": conflict_op,
                "conflict_type": "master_is_existing_slave",
                "conflict_reason": f"New operation's master device {new_master} is a slave device in existing operation",
                "violated_rule": "Rule 1: master cannot be an existing operation's slave",
            }

        # Rule 2: Check if new slave is used in existing operations (either as master or slave)
        if new_slave and new_slave in all_used_devices:
            conflict_op = self._find_operation_by_device(new_slave)
            conflict_type = "slave_in_use"

            if new_slave in existing_masters:
                conflict_reason = f"New operation's slave device {new_slave} is a master device in existing operation"
                violated_rule = "Rule 2: slave cannot be an existing operation's master"
            else:
                conflict_reason = f"New operation's slave device {new_slave} is a slave device in existing operation"
                violated_rule = "Rule 2: slave cannot be an existing operation's slave"

            _LOGGER.warning("Conflict! %s", conflict_reason)
            return {
                "has_conflict": True,
                "conflicting_operation": conflict_op,
                "conflict_type": conflict_type,
                "conflict_reason": conflict_reason,
                "violated_rule": violated_rule,
            }

        # No conflict
        _LOGGER.debug("New operation passed all conflict checks")
        return {
            "has_conflict": False,
            "conflicting_operation": None,
            "conflict_type": "no_conflict",
            "conflict_reason": "Passed all conflict check rules",
        }

    def _find_operation_by_slave(self, slave_device_id: str) -> Optional[str]:
        """Find corresponding operation ID by slave device ID"""
        for op_id, operation in self._pending_operations.items():
            if operation.get("slave") == slave_device_id:
                return op_id
        return None

    def _find_operation_by_device(self, device_id: str) -> Optional[str]:
        """Find corresponding operation ID by device ID (device could be master or slave)"""
        for op_id, operation in self._pending_operations.items():
            if (
                operation.get("master") == device_id
                or operation.get("slave") == device_id
            ):
                return op_id
        return None

    def _log_detailed_conflict_analysis(self, new_operation: Dict):
        """Record detailed conflict analysis (for debugging)"""
        new_master = new_operation.get("master")
        new_slave = new_operation.get("slave")

        _LOGGER.debug("=== Detailed Conflict Analysis ===")
        _LOGGER.debug("New operation: master=%s, slave=%s", new_master, new_slave)

        # Analyze each existing operation
        for op_id, operation in self._pending_operations.items():
            existing_master = operation.get("master")
            existing_slave = operation.get("slave")

            master_conflict = new_master == existing_slave
            slave_conflict_master = new_slave == existing_master
            slave_conflict_slave = new_slave == existing_slave

            conflicts = []
            if master_conflict:
                conflicts.append("New master is existing slave")
            if slave_conflict_master:
                conflicts.append("New slave is existing master")
            if slave_conflict_slave:
                conflicts.append("New slave is existing slave")

            if conflicts:
                _LOGGER.debug(
                    "Conflict with operation %s: %s (Existing: master=%s, slave=%s)",
                    op_id,
                    " | ".join(conflicts),
                    existing_master,
                    existing_slave,
                )
            else:
                _LOGGER.debug(
                    "No conflict with operation %s (Existing: master=%s, slave=%s)",
                    op_id,
                    existing_master,
                    existing_slave,
                )

        _LOGGER.debug("=== Analysis End ===")

    async def async_start_operation_processing(self, operation_id: str):
        """Start operation processing (includes polling status check)"""
        operation = self._pending_operations.get(operation_id)
        if not operation:
            return

        callback_func = operation.get("request_callback")

        try:
            # Notify operation start execution
            if callback_func:
                await callback_func(
                    {
                        "status": "executing",
                        "operation_id": operation_id,
                        "extra": {
                            "timestamp": datetime.now().isoformat(),
                        },
                    },
                )

            # Execute actual operation
            execution_success = await self._execute_operation(operation)

            if not execution_success:
                # Execution failed, notify immediately
                if callback_func:
                    await callback_func(
                        {
                            "status": "execution_failed",
                            "operation_id": operation_id,
                            "extra": {
                                "timestamp": datetime.now().isoformat(),
                            },
                        },
                    )
                await self._handle_operation_failed(operation_id, "execution_failed")
                return

            # Execution successful, start polling status check
            if callback_func:
                await callback_func(
                    {
                        "status": "verifying",
                        "operation_id": operation_id,
                        "extra": {
                            "timestamp": datetime.now().isoformat(),
                        },
                    },
                )

            # Start polling task
            self._poll_tasks[operation_id] = asyncio.create_task(
                self._poll_operation_status_with_callback(operation_id)
            )

        except Exception as e:
            _LOGGER.error("Operation processing exception: %s - %s", operation_id, e)

            if callback_func:
                await callback_func(
                    {
                        "status": "error",
                        "operation_id": operation_id,
                        "extra": {
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        },
                    },
                )

            await self._handle_operation_failed(operation_id, f"exception: {str(e)}")

    async def _poll_operation_status_with_callback(self, operation_id: str):
        """Poll operation status and notify progress via callback"""
        operation = self._pending_operations.get(operation_id)
        if not operation:
            return

        callback_func = operation.get("request_callback")

        _LOGGER.debug("start polling: %s", operation_id)

        while operation_id in self._pending_operations:
            try:
                # Check timeout
                time_since_start = (
                    datetime.now() - operation["start_time"]
                ).total_seconds()
                if time_since_start > self._operation_timeout:
                    _LOGGER.warning(
                        "Operation timeout: %s (duration: %.1f seconds)",
                        operation_id,
                        time_since_start,
                    )

                    if callback_func:
                        await callback_func(
                            {
                                "status": "timeout",
                                "operation_id": operation_id,
                                "extra": {
                                    "duration": time_since_start,
                                    "timestamp": datetime.now().isoformat(),
                                },
                            },
                        )

                    await self._handle_operation_timeout(operation_id)
                    break

                # Check retry count
                if operation["retry_count"] >= self._max_retries:
                    _LOGGER.warning("Maximum retries reached: %s", operation_id)

                    if callback_func:
                        await callback_func(
                            {
                                "status": "max_retries_exceeded",
                                "operation_id": operation_id,
                                "extra": {
                                    "retry_count": operation["retry_count"],
                                    "timestamp": datetime.now().isoformat(),
                                },
                            },
                        )

                    await self._handle_operation_failed(operation_id, "max_retries")
                    break

                # Update status
                operation["status"] = "verifying"
                operation["retry_count"] += 1
                operation["last_check"] = datetime.now()

                _LOGGER.debug(
                    "Polling operation %s (attempt %d/%d)",
                    operation_id,
                    operation["retry_count"],
                    self._max_retries,
                )

                # Notify polling progress
                if callback_func:
                    await callback_func(
                        {
                            "status": "verifying",
                            "operation_id": operation_id,
                            "extra": {
                                "retry_count": operation["retry_count"],
                                "max_retries": self._max_retries,
                                "timestamp": datetime.now().isoformat(),
                            },
                        },
                    )

                # Verify operation status
                is_success = await self._verify_operation_state(operation)

                if is_success:
                    # Operation successful
                    _LOGGER.debug("verify ok for operation_id: %s", operation_id)

                    oper_type = operation.get("type")
                    if oper_type == "remove_slave":
                        await asyncio.sleep(
                            10
                        )  # Wait longer after removing slave device to ensure status update

                    if callback_func:
                        await callback_func(
                            {
                                "status": "success",
                                "operation_id": operation_id,
                                "extra": {
                                    "retry_count": operation["retry_count"],
                                    "duration": time_since_start,
                                    "timestamp": datetime.now().isoformat(),
                                },
                            },
                        )

                    await self._handle_operation_success(operation_id)
                    break

                # Wait for next polling round
                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                _LOGGER.debug("Polling task cancelled: %s", operation_id)

                if callback_func:
                    await callback_func(
                        {
                            "status": "cancelled",
                            "operation_id": operation_id,
                            "extra": {
                                "timestamp": datetime.now().isoformat(),
                            },
                        },
                    )
                break

            except Exception as e:
                _LOGGER.error("Polling operation exception: %s - %s", operation_id, e)

                if callback_func:
                    await callback_func(
                        {
                            "status": "polling_error",
                            "operation_id": operation_id,
                            "extra": {
                                "error": str(e),
                                "timestamp": datetime.now().isoformat(),
                            },
                        },
                    )

                await asyncio.sleep(self._poll_interval)

        # Clean up task
        if operation_id in self._poll_tasks:
            del self._poll_tasks[operation_id]

    async def _execute_operation(self, operation: Dict) -> bool:
        """Execute specific operation"""
        op_type = operation.get("type")
        master = operation.get("master")
        slave = operation.get("slave")
        operation_data = operation.get("data", {})

        try:
            if op_type == "set_slave":
                # return (
                #     await self.device_manager.speaker_manager.async_set_slave_speaker(
                #         master, slave
                #     )
                # )
                try:
                    params = operation_data.get("params", {})
                    required_keys = (
                        "slave_ip", "ssid", "wifi_channel", "auth",
                        "encry", "psk", "master_ip", "uuid",
                    )
                    missing = [k for k in required_keys if k not in params]
                    if missing:
                        _LOGGER.error(
                            "Missing required params for set_slave: %s", missing
                        )
                        return False
                    slave_ip = params["slave_ip"]
                    ssid = params["ssid"]
                    wifi_channel = params["wifi_channel"]
                    auth = params["auth"]
                    encry = params["encry"]
                    psk = params["psk"]
                    master_ip = params["master_ip"]
                    uuid = params["uuid"]
                    ssid_hex = binascii.hexlify(ssid.encode()).decode()
                    # await set_slave_device(
                    #     slave_ip,
                    #     ssid_hex,
                    #     wifi_channel,
                    #     auth,
                    #     encry,
                    #     psk,
                    #     master_ip,
                    #     uuid,
                    # )
                    async with HivicoClient(timeout=5, debug=True) as client:
                        await client.connect_slave_to_master(
                            slave_ip=slave_ip,
                            ssid=ssid_hex,
                            wifi_channel=wifi_channel,
                            auth=auth,
                            encry=encry,
                            psk=psk,
                            master_ip=master_ip,
                            uuid=uuid,
                        )
                    return True
                except Exception as e:
                    _LOGGER.error("Failed to set slave speaker operation: %s", e)
                    return False
            elif op_type == "remove_slave":
                # return await self.device_manager.speaker_manager.async_remove_slave_speaker(
                #     master, slave
                # )
                try:
                    params = operation_data.get("params", {})
                    required_keys = ("master_ip", "slave_ip_ra0")
                    missing = [k for k in required_keys if k not in params]
                    if missing:
                        _LOGGER.error(
                            "Missing required params for remove_slave: %s", missing
                        )
                        return False
                    master_ip = params["master_ip"]
                    slave_ip_ra0 = params["slave_ip_ra0"]
                    # await remove_slave_device(master_ip, slave_ip_ra0)
                    async with HivicoClient(timeout=5, debug=True) as client:
                        await client.remove_slave_from_group(master_ip, slave_ip_ra0)
                    return True
                except Exception as e:
                    _LOGGER.error("Failed to set slave speaker operation: %s", e)
                    return False
            else:
                _LOGGER.error("Unknown operation type: %s", op_type)
                return False
        except Exception as e:
            _LOGGER.error("Operation execution exception: %s", e)
            return False

    # Modify original success/failure handling methods to include callback notifications
    async def _handle_operation_success(self, operation_id: str):
        """Handle operation success"""
        operation = self._pending_operations.get(operation_id)
        if not operation:
            return

        # Update operation status
        operation["status"] = "success"
        operation["end_time"] = datetime.now()
        duration = (operation["end_time"] - operation["start_time"]).total_seconds()

        _LOGGER.debug(
            "operation successfully: %s (time: %.1f seconds, try num: %d)",
            operation_id,
            duration,
            operation["retry_count"],
        )

        # Send operation success event
        self.hass.bus.async_fire(
            f"{DOMAIN}_group_operation_succeeded",
            {
                "operation_id": operation_id,
                "master": operation["master"],
                "slave": operation["slave"],
                "action": operation["type"],
                "duration": duration,
                "retry_count": operation["retry_count"],
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Trigger immediate discovery to ensure status synchronization
        _LOGGER.debug("Trigger immediate discovery to synchronize status")
        # self.discovery_scheduler.schedule_immediate_discovery(force=False)

        # Clean up operation
        await self._cleanup_operation(operation_id)

    async def _handle_operation_timeout(self, operation_id: str):
        """Handle operation timeout"""
        operation = self._pending_operations.get(operation_id)
        if not operation:
            return

        # Update operation status
        operation["status"] = "timeout"
        operation["end_time"] = datetime.now()

        _LOGGER.warning("Operation timeout: %s", operation_id)

        # Send operation timeout event
        self.hass.bus.async_fire(
            f"{DOMAIN}_group_operation_timeout",
            {
                "operation_id": operation_id,
                "master": operation["master"],
                "slave": operation["slave"],
                "action": operation["type"],
                "duration": self._operation_timeout,
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Even if timeout, trigger discovery to get current status
        _LOGGER.debug("Operation timeout, trigger discovery to get current status")
        # self.discovery_scheduler.schedule_immediate_discovery(force=False)

        # Clean up operation
        await self._cleanup_operation(operation_id)

    async def _cleanup_operation(self, operation_id: str):
        """Clean up operation (includes callback cleanup)"""
        # Delay cleanup to give event handling time
        await asyncio.sleep(1)

        # Clean up callbacks
        if operation_id in self._request_callbacks:
            del self._request_callbacks[operation_id]

        # Clean up operations and tasks
        if operation_id in self._pending_operations:
            del self._pending_operations[operation_id]

        if operation_id in self._poll_tasks:
            task = self._poll_tasks[operation_id]
            if not task.done():
                task.cancel()
            del self._poll_tasks[operation_id]

    async def _poll_operation_status(self, operation_id: str):
        """Poll operation status (every 2 seconds)"""
        operation = self._pending_operations.get(operation_id)
        if not operation:
            _LOGGER.warning("Operation does not exist: %s", operation_id)
            return

        _LOGGER.info("Start polling operation status: %s", operation_id)

        while operation_id in self._pending_operations:
            try:
                # Check timeout
                time_since_start = (
                    datetime.now() - operation["start_time"]
                ).total_seconds()
                if time_since_start > self._operation_timeout:
                    _LOGGER.warning(
                        "Operation timeout: %s (duration: %.1f seconds)",
                        operation_id,
                        time_since_start,
                    )
                    await self._handle_operation_timeout(operation_id)
                    break

                # Check retry count
                if operation["retry_count"] >= self._max_retries:
                    _LOGGER.warning("Maximum retries reached: %s", operation_id)
                    await self._handle_operation_failed(operation_id, "max_retries")
                    break

                # Update status
                operation["status"] = "verifying"
                operation["retry_count"] += 1
                operation["last_check"] = datetime.now()

                _LOGGER.debug(
                    "Polling operation %s (attempt %d/%d)",
                    operation_id,
                    operation["retry_count"],
                    self._max_retries,
                )

                # Verify operation status
                is_success = await self._verify_operation_state(operation)

                if is_success:
                    # Operation successful
                    await self._handle_operation_success(operation_id)
                    break

                # Wait for next polling round
                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                _LOGGER.debug("Polling task cancelled: %s", operation_id)
                break
            except Exception as e:
                _LOGGER.error("Polling operation exception: %s - %s", operation_id, e)
                await asyncio.sleep(self._poll_interval)

        # Clean up task
        if operation_id in self._poll_tasks:
            del self._poll_tasks[operation_id]

    async def _verify_operation_state(self, operation: Dict) -> bool:
        """Verify operation status"""
        master_speaker_device_id = operation["master"]
        slave_speaker_device_id = operation["slave"]
        expected_state = operation["expected_state"]

        try:
            """
            The following processing is not yet perfect, should distinguish by type
            When type is set_slave, read slave list through master to see if target device has become master's slave
            When type is remove_slave, directly query slave to see if it has become independent (note that http may not be connectable initially, may need multiple attempts)
            """

            type = operation.get("type")
            operation_data = operation.get("data", {})
            params = operation_data.get("params", {})
            master_ip = params.get("master_ip", None)
            if master_ip is None:
                _LOGGER.error("master_ip is None")
                return False
            if type == "set_slave":
                try:
                    # slave_device_result = await get_slave_devices(master_ip)
                    slave_device_result = None
                    async with HivicoClient(timeout=5, debug=True) as client:
                        slave_device_result = await client.get_slave_devices(master_ip)
                    if slave_device_result is None:
                        _LOGGER.error("slave_device_result is None")
                        return False
                    slave_list = slave_device_result.get("slave_list", [])
                    if slave_list is None:
                        _LOGGER.error("slave_list is None")
                        return False
                    for slave in slave_list:
                        uuid = slave.get("uuid")
                        _LOGGER.debug("check slave get UUID: %s", uuid)
                        if uuid == slave_speaker_device_id:
                            _LOGGER.debug("find match UUID: %s", uuid)
                            return True
                    return False
                except Exception as e:
                    _LOGGER.error("Failed to get slave speaker list: %s", e)
                    return False
            elif type == "remove_slave":
                try:
                    # slave_device_result = await get_slave_devices(master_ip)
                    slave_device_result = None
                    async with HivicoClient(timeout=5, debug=True) as client:
                        slave_device_result = await client.get_slave_devices(master_ip)
                    if slave_device_result is None:
                        _LOGGER.error("slave_device_result is None")
                        return False
                    slave_list = slave_device_result.get("slave_list", [])
                    if slave_list is None:
                        _LOGGER.error("slave_list is None")
                        return False
                    still_exists = False
                    for slave in slave_list:
                        uuid = slave.get("uuid")
                        _LOGGER.debug("check slave get UUID: %s", uuid)
                        if uuid == slave_speaker_device_id:
                            _LOGGER.debug("find match UUID: %s", uuid)
                            still_exists = True
                            break
                    if still_exists:
                        return False
                    else:
                        return True
                except Exception as e:
                    _LOGGER.error("Failed to get slave speaker list: %s", e)
                    return False


        except Exception as e:
            _LOGGER.error("Exception verifying operation status: %s", e)
            return False

    async def _check_actual_state(
        self, master_client, slave_speaker_device_id: str
    ) -> str:
        """Check actual status"""
        try:
            # Get slave speaker list
            slave_devices = await master_client.state.async_get_slave_devices(timeout=3)
            if slave_devices is None:
                return "unknown"

            if slave_speaker_device_id in slave_devices:
                return "slave"
            else:
                return "standalone"

        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout getting slave speaker list")
            return "unknown"
        except Exception as e:
            _LOGGER.debug("Exception getting slave speaker list: %s", e)
            return "unknown"

    async def _handle_operation_failed(self, operation_id: str, reason: str):
        """Handle operation failure"""
        operation = self._pending_operations.get(operation_id)
        if not operation:
            return

        # Update operation status
        operation["status"] = "failed"
        operation["end_time"] = datetime.now()
        operation["failure_reason"] = reason

        _LOGGER.error("Operation failed: %s (reason: %s)", operation_id, reason)

        # Send operation failure event
        self.hass.bus.async_fire(
            f"{DOMAIN}_group_operation_failed",
            {
                "operation_id": operation_id,
                "master": operation["master"],
                "slave": operation["slave"],
                "action": operation["type"],
                "reason": reason,
                "retry_count": operation["retry_count"],
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Clean up operation
        await self._cleanup_operation(operation_id)

    @callback
    def _handle_operation_started(self, event):
        """Handle operation start event"""
        operation_id = event.data.get("operation_id")
        _LOGGER.debug("Group operation started: %s", operation_id)

    @callback
    def _handle_device_updated(self, event):
        """Handle device update event"""
        # When device status updates, check if it affects ongoing operations
        speaker_device_id = event.data.get("speaker_device_id")

        # Check all pending operations to see if related to this device
        for operation_id, operation in list(self._pending_operations.items()):
            if speaker_device_id in (operation["master"], operation["slave"]):
                _LOGGER.debug(
                    "Related device status update: %s, operation: %s",
                    speaker_device_id,
                    operation_id,
                )

    async def get_operation_status(self, operation_id: str) -> Optional[Dict]:
        """Get operation status"""
        operation = self._pending_operations.get(operation_id)
        if not operation:
            return None

        result = operation.copy()

        # Calculate duration
        if "start_time" in result:
            start_time = result["start_time"]
            end_time = result.get("end_time", datetime.now())
            result["duration"] = (end_time - start_time).total_seconds()

        # Clean up unnecessary fields
        result.pop("start_time", None)
        result.pop("end_time", None)
        result.pop("last_check", None)

        return result

    async def get_all_operations(self) -> Dict[str, Dict]:
        """Get all operation statuses"""
        results = {}

        for operation_id, operation in self._pending_operations.items():
            results[operation_id] = await self.get_operation_status(operation_id)

        return results

    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel operation"""
        if operation_id not in self._pending_operations:
            return False

        operation = self._pending_operations[operation_id]

        _LOGGER.info("Cancel operation: %s", operation_id)

        # Send cancellation event
        self.hass.bus.async_fire(
            f"{DOMAIN}_group_operation_cancelled",
            {
                "operation_id": operation_id,
                "master": operation["master"],
                "slave": operation["slave"],
                "action": operation["type"],
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Clean up operation
        await self._cleanup_operation(operation_id)

        return True
