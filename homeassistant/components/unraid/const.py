"""Constants for the Unraid integration."""

from typing import Final

# =============================================================================
# Integration Info
# =============================================================================
DOMAIN: Final = "unraid"
INTEGRATION_VERSION: Final = "2026.01.0"
MANUFACTURER: Final = "Lime Technology"

# =============================================================================
# Configuration Keys
# =============================================================================
CONF_SYSTEM_INTERVAL: Final = "system_interval"
CONF_STORAGE_INTERVAL: Final = "storage_interval"
CONF_UPS_CAPACITY_VA: Final = "ups_capacity_va"
CONF_UPS_NOMINAL_POWER: Final = "ups_nominal_power"

# =============================================================================
# Default Values
# =============================================================================
DEFAULT_SYSTEM_POLL_INTERVAL: Final = 30  # seconds
DEFAULT_STORAGE_POLL_INTERVAL: Final = 300  # seconds (5 minutes)
DEFAULT_UPS_CAPACITY_VA: Final = 0  # 0 = informational only
DEFAULT_UPS_NOMINAL_POWER: Final = 0  # 0 = disabled, user must set for UPS Power sensor

# =============================================================================
# Platforms
# =============================================================================
PLATFORMS: list[str] = []

# =============================================================================
# Entity Keys (for coordinator data)
# =============================================================================
KEY_SYSTEM: Final = "system"
KEY_ARRAY: Final = "array"
KEY_DISKS: Final = "disks"
KEY_SHARES: Final = "shares"
KEY_CONTAINERS: Final = "containers"
KEY_VMS: Final = "vms"
KEY_UPS: Final = "ups"
KEY_NOTIFICATIONS: Final = "notifications"

# =============================================================================
# Sensor Types
# =============================================================================
SENSOR_CPU_USAGE: Final = "cpu_usage"
SENSOR_RAM_USAGE: Final = "ram_usage"
SENSOR_CPU_TEMP: Final = "cpu_temperature"
SENSOR_CPU_POWER: Final = "cpu_power"
SENSOR_UPTIME: Final = "uptime"
SENSOR_ARRAY_STATE: Final = "array_state"
SENSOR_ARRAY_USAGE: Final = "array_usage"
SENSOR_PARITY_PROGRESS: Final = "parity_progress"
SENSOR_DISK_TEMP: Final = "disk_temperature"
SENSOR_DISK_USAGE: Final = "disk_usage"
SENSOR_DISK_HEALTH: Final = "disk_health"
SENSOR_UPS_BATTERY: Final = "ups_battery"
SENSOR_UPS_LOAD: Final = "ups_load"
SENSOR_UPS_RUNTIME: Final = "ups_runtime"
SENSOR_UPS_POWER: Final = "ups_power"
SENSOR_SHARE_USAGE: Final = "share_usage"
SENSOR_FLASH_USAGE: Final = "flash_usage"
SENSOR_NOTIFICATIONS: Final = "active_notifications"

# =============================================================================
# Binary Sensor Types
# =============================================================================
BINARY_SENSOR_ARRAY_STARTED: Final = "array_started"
BINARY_SENSOR_PARITY_CHECK_RUNNING: Final = "parity_check_running"
BINARY_SENSOR_PARITY_VALID: Final = "parity_valid"
BINARY_SENSOR_DISK_HEALTH: Final = "disk_health"
BINARY_SENSOR_DISK_STANDBY: Final = "disk_standby"
BINARY_SENSOR_UPS_CONNECTED: Final = "ups_connected"

# =============================================================================
# Switch Types
# =============================================================================
SWITCH_CONTAINER: Final = "container"
SWITCH_VM: Final = "vm"

# =============================================================================
# Button Types
# =============================================================================
BUTTON_ARRAY_START: Final = "array_start"
BUTTON_ARRAY_STOP: Final = "array_stop"
BUTTON_PARITY_CHECK_START: Final = "parity_check_start"
BUTTON_PARITY_CHECK_STOP: Final = "parity_check_stop"
BUTTON_DISK_SPIN_UP: Final = "disk_spin_up"
BUTTON_DISK_SPIN_DOWN: Final = "disk_spin_down"

# =============================================================================
# Icons - Material Design Icons (mdi:)
# =============================================================================
# System
ICON_CPU: Final = "mdi:cpu-64-bit"
ICON_MEMORY: Final = "mdi:memory"
ICON_TEMPERATURE: Final = "mdi:thermometer"
ICON_POWER: Final = "mdi:lightning-bolt"
ICON_UPTIME: Final = "mdi:clock-outline"

# Storage
ICON_ARRAY: Final = "mdi:harddisk"
ICON_PARITY: Final = "mdi:shield-check"
ICON_PARITY_SYNC: Final = "mdi:shield-sync"
ICON_HARDDISK: Final = "mdi:harddisk"
ICON_SHARE: Final = "mdi:folder-network"
ICON_FLASH: Final = "mdi:usb-flash-drive"
ICON_DATABASE: Final = "mdi:database"
ICON_HEART_PULSE: Final = "mdi:heart-pulse"
ICON_PROGRESS: Final = "mdi:progress-check"

# Docker & VMs
ICON_CONTAINER: Final = "mdi:docker"
ICON_VM: Final = "mdi:desktop-tower"

# UPS
ICON_UPS: Final = "mdi:battery"
ICON_UPS_BATTERY: Final = "mdi:battery"
ICON_UPS_LOAD: Final = "mdi:gauge"
ICON_UPS_RUNTIME: Final = "mdi:timer"

# Network
ICON_NETWORK: Final = "mdi:ethernet"

# Notifications
ICON_NOTIFICATION: Final = "mdi:bell"
ICON_NOTIFICATION_ALERT: Final = "mdi:bell-alert"

# Button/Control Icons
ICON_PLAY: Final = "mdi:play"
ICON_STOP: Final = "mdi:stop"
ICON_PAUSE: Final = "mdi:pause"
ICON_RESTART: Final = "mdi:restart"
ICON_SPIN_UP: Final = "mdi:rotate-right"
ICON_SPIN_DOWN: Final = "mdi:sleep"

# =============================================================================
# Attributes
# =============================================================================
# System attributes
ATTR_HOSTNAME: Final = "hostname"
ATTR_VERSION: Final = "version"
ATTR_CPU_MODEL: Final = "cpu_model"
ATTR_CPU_CORES: Final = "cpu_cores"
ATTR_CPU_THREADS: Final = "cpu_threads"
ATTR_RAM_TOTAL: Final = "ram_total"

# Array attributes
ATTR_ARRAY_STATE: Final = "array_state"
ATTR_NUM_DISKS: Final = "num_disks"
ATTR_NUM_DATA_DISKS: Final = "num_data_disks"
ATTR_NUM_PARITY_DISKS: Final = "num_parity_disks"
ATTR_PARITY_STATUS: Final = "parity_status"
ATTR_PARITY_CHECK_STATUS: Final = "parity_check_status"

# Disk attributes
ATTR_SMART_STATUS: Final = "smart_status"
ATTR_SMART_ERRORS: Final = "smart_errors"
ATTR_SPIN_STATE: Final = "spin_state"

# Container attributes
ATTR_CONTAINER_ID: Final = "container_id"
ATTR_CONTAINER_IMAGE: Final = "container_image"
ATTR_CONTAINER_STATUS: Final = "container_status"
ATTR_CONTAINER_PORTS: Final = "container_ports"

# VM attributes
ATTR_VM_ID: Final = "vm_id"
ATTR_VM_VCPUS: Final = "vm_vcpus"
ATTR_VM_MEMORY: Final = "vm_memory"

# UPS attributes
ATTR_UPS_STATUS: Final = "ups_status"
ATTR_UPS_MODEL: Final = "ups_model"

# Network attributes
ATTR_NETWORK_MAC: Final = "network_mac"
ATTR_NETWORK_IP: Final = "network_ip"
ATTR_NETWORK_SPEED: Final = "network_speed"

# =============================================================================
# Error Messages
# =============================================================================
ERROR_CANNOT_CONNECT: Final = "cannot_connect"
ERROR_INVALID_AUTH: Final = "invalid_auth"
ERROR_UNKNOWN: Final = "unknown"
ERROR_TIMEOUT: Final = "timeout"
ERROR_ALREADY_CONFIGURED: Final = "already_configured"
ERROR_CONTROL_FAILED: Final = "control_failed"

# =============================================================================
# State Values (for consistent state comparisons)
# =============================================================================
# Array states
STATE_ARRAY_STARTED: Final = "STARTED"
STATE_ARRAY_STOPPED: Final = "STOPPED"

# Container states
STATE_CONTAINER_RUNNING: Final = "RUNNING"
STATE_CONTAINER_PAUSED: Final = "PAUSED"
STATE_CONTAINER_EXITED: Final = "EXITED"

# VM states
STATE_VM_RUNNING: Final = "RUNNING"
STATE_VM_IDLE: Final = "IDLE"
STATE_VM_PAUSED: Final = "PAUSED"
STATE_VM_SHUTOFF: Final = "SHUTOFF"

# Running states for VMs (states where VM is considered "on")
VM_RUNNING_STATES: Final = frozenset({STATE_VM_RUNNING, STATE_VM_IDLE})

# =============================================================================
# Repair Issue IDs
# =============================================================================
REPAIR_AUTH_FAILED: Final = "auth_failed"
REPAIR_CONNECTIVITY: Final = "connectivity_issue"

# =============================================================================
# Parallel Updates (one at a time per platform to avoid API overload)
# =============================================================================
PARALLEL_UPDATES: Final = 1
