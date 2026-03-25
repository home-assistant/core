"""Configuration Flow Enhancement for Heiman Home Integration.

Provides enhanced configuration features:
- Network detection and validation
- Advanced device filtering UI
- Multi-home selection
- Confirmation step
- Progress tracking
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


@dataclass
class NetworkDetectionResult:
    """Network detection result."""

    address: str
    success: bool
    latency_ms: float = 0.0
    error_message: str | None = None


@dataclass
class DeviceFilterConfig:
    """Device filter configuration."""

    filter_mode: str = "exclude"  # include or exclude
    statistics_logic: str = "or"  # and or or
    room_filter_mode: str = "exclude"
    room_list: list[str] = field(default_factory=list)
    type_filter_mode: str = "exclude"
    type_list: list[str] = field(default_factory=list)
    model_filter_mode: str = "exclude"
    model_list: list[str] = field(default_factory=list)
    device_filter_mode: str = "exclude"
    device_list: list[str] = field(default_factory=list)


@dataclass
class AdvancedOptions:
    """Advanced configuration options."""

    hide_non_standard_entities: bool = False
    action_debug_mode: bool = False
    binary_sensor_display_mode: str = "bool"  # bool or text
    display_devices_changed_notify: list[str] = field(default_factory=list)
    device_filter_config: DeviceFilterConfig | None = None


@dataclass
class ConfigSummary:
    """Configuration summary for confirmation step."""

    user_id: str
    cloud_server: str
    integration_language: str
    selected_homes: list[dict[str, Any]]
    total_devices: int
    filtered_devices: int
    advanced_options: AdvancedOptions

    def get_home_names(self) -> str:
        """Get formatted home names string."""
        return ", ".join(
            [home.get("homeName", "Unknown") for home in self.selected_homes],
        )

    def get_summary_text(self) -> str:
        """Get summary text for confirmation."""
        return (
            f"**User ID:** {self.user_id}\n"
            f"**Cloud Server:** {self.cloud_server}\n"
            f"**Language:** {self.integration_language}\n"
            f"**Homes:** {self.get_home_names()}\n"
            f"**Total Devices:** {self.total_devices}\n"
            f"**Filtered Devices:** {self.filtered_devices}"
        )


class NetworkDetector:
    """Network connectivity detector."""

    # Default detection addresses
    DEFAULT_ADDRESSES = [
        "8.8.8.8",  # Google DNS
        "1.1.1.1",  # Cloudflare DNS
        "https://www.google.com",
        "https://www.cloudflare.com",
    ]

    # OAuth2 and API endpoints to check
    DEPENDENCY_ENDPOINTS = {
        "oauth2": "https://account.heiman.cn/oauth2/authorize",
        "http_api": "https://api.heiman.cn/api-app",
        "mqtt": "mqtt.heiman.cn:1883",
    }

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        """Initialize network detector.

        Args:
            loop: Event loop
        """
        self._loop = loop or asyncio.get_running_loop()
        self._results: list[NetworkDetectionResult] = []

    async def detect_network(
        self,
        custom_addresses: list[str] | None = None,
    ) -> list[NetworkDetectionResult]:
        """Detect network connectivity.

        Args:
            custom_addresses: Custom addresses to test

        Returns:
            List of detection results
        """
        addresses = custom_addresses or self.DEFAULT_ADDRESSES
        self._results = []

        tasks = []
        for addr in addresses:
            if addr.startswith(("http://", "https://")):
                tasks.append(self._detect_http(addr))
            else:
                tasks.append(self._detect_ping(addr))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._results.append(
                    NetworkDetectionResult(
                        address=addresses[i],
                        success=False,
                        error_message=str(result),
                    ),
                )
            elif isinstance(result, NetworkDetectionResult):
                self._results.append(result)

        return self._results

    async def _detect_ping(self, address: str) -> NetworkDetectionResult:
        """Detect connectivity via ping.

        Args:
            address: IP address or hostname

        Returns:
            Detection result
        """
        try:
            # Use asyncio to run ping command
            process = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                "1",
                "-W",
                "2",
                address,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=5)

            if process.returncode == 0:
                # Parse latency from output
                latency = self._parse_ping_latency(stdout.decode())
                return NetworkDetectionResult(
                    address=address,
                    success=True,
                    latency_ms=latency,
                )
            return NetworkDetectionResult(
                address=address,
                success=False,
                error_message=f"Ping failed with code {process.returncode}",
            )

        except TimeoutError:
            return NetworkDetectionResult(
                address=address,
                success=False,
                error_message="Ping timeout",
            )
        except Exception as err:  # noqa: BLE001
            return NetworkDetectionResult(
                address=address,
                success=False,
                error_message=str(err),
            )

    async def _detect_http(self, url: str) -> NetworkDetectionResult:
        """Detect connectivity via HTTP GET.

        Args:
            url: HTTP/HTTPS URL

        Returns:
            Detection result
        """
        try:
            async with aiohttp.ClientSession() as session:
                start_time = asyncio.get_event_loop().time()

                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000

                    if response.status < 400:
                        return NetworkDetectionResult(
                            address=url,
                            success=True,
                            latency_ms=round(latency, 2),
                        )
                    return NetworkDetectionResult(
                        address=url,
                        success=False,
                        error_message=f"HTTP {response.status}",
                    )

        except TimeoutError:
            return NetworkDetectionResult(
                address=url,
                success=False,
                error_message="HTTP timeout",
            )
        except Exception as err:  # noqa: BLE001
            return NetworkDetectionResult(
                address=url,
                success=False,
                error_message=str(err),
            )

    def _parse_ping_latency(self, output: str) -> float:
        """Parse latency from ping output.

        Args:
            output: Ping command output

        Returns:
            Latency in milliseconds
        """
        # Try to parse time=X.XXX ms
        match = re.search(r"time[=<](\d+\.?\d*)\s*ms", output)
        if match:
            return float(match.group(1))

        return 0.0

    async def check_dependencies(self) -> dict[str, bool]:
        """Check dependency endpoints.

        Returns:
            Dict of endpoint name -> availability
        """
        results = {}

        for name, endpoint in self.DEPENDENCY_ENDPOINTS.items():
            try:
                if endpoint.startswith(("http://", "https://")):
                    result = await self._detect_http(endpoint)
                    results[name] = result.success
                else:
                    # For MQTT, just check if we can resolve
                    result = await self._detect_ping(endpoint.split(":")[0])
                    results[name] = result.success
            except Exception:  # noqa: BLE001
                results[name] = False

        return results

    def get_detection_summary(self) -> str:
        """Get detection summary.

        Returns:
            Summary string
        """
        total = len(self._results)
        success = sum(1 for r in self._results if r.success)

        if total == 0:
            return "No tests performed"

        if success == total:
            return f"All {total} tests passed ✓"

        return f"{success}/{total} tests passed"


class ConfigFlowEnhanced:
    """Enhanced configuration flow manager."""

    def __init__(self) -> None:
        """Initialize config flow enhancer."""
        self._network_detector: NetworkDetector | None = None
        self._advanced_options = AdvancedOptions()
        self._config_summary: ConfigSummary | None = None

    def init_network_detector(self) -> None:
        """Initialize network detector."""
        self._network_detector = NetworkDetector()

    async def perform_network_detection(
        self,
        custom_addresses: list[str] | None = None,
    ) -> list[NetworkDetectionResult]:
        """Perform network detection.

        Args:
            custom_addresses: Custom addresses to test

        Returns:
            List of detection results
        """
        if not self._network_detector:
            self.init_network_detector()

        return await self._network_detector.detect_network(custom_addresses)

    async def check_network_dependencies(self) -> dict[str, bool]:
        """Check network dependencies.

        Returns:
            Dict of dependency name -> availability
        """
        if not self._network_detector:
            self.init_network_detector()

        return await self._network_detector.check_dependencies()

    def configure_advanced_options(
        self,
        hide_non_standard: bool = False,
        action_debug: bool = False,
        binary_mode: str = "bool",
        notify_changes: list[str] | None = None,
        filter_config: DeviceFilterConfig | None = None,
    ) -> None:
        """Configure advanced options.

        Args:
            hide_non_standard: Hide non-standard entities
            action_debug: Enable action debug mode
            binary_mode: Binary sensor display mode
            notify_changes: List of change notifications to display
            filter_config: Device filter configuration
        """
        self._advanced_options.hide_non_standard_entities = hide_non_standard
        self._advanced_options.action_debug_mode = action_debug
        self._advanced_options.binary_sensor_display_mode = binary_mode

        if notify_changes is not None:
            self._advanced_options.display_devices_changed_notify = notify_changes

        if filter_config:
            self._advanced_options.device_filter_config = filter_config

    def create_config_summary(
        self,
        user_id: str,
        cloud_server: str,
        integration_language: str,
        selected_homes: list[dict[str, Any]],
        total_devices: int,
        filtered_devices: int = 0,
    ) -> ConfigSummary:
        """Create configuration summary.

        Args:
            user_id: User identifier
            cloud_server: Cloud server region
            integration_language: Integration language
            selected_homes: List of selected homes
            total_devices: Total number of devices
            filtered_devices: Number of devices after filtering

        Returns:
            Configuration summary
        """
        self._config_summary = ConfigSummary(
            user_id=user_id,
            cloud_server=cloud_server,
            integration_language=integration_language,
            selected_homes=selected_homes,
            total_devices=total_devices,
            filtered_devices=filtered_devices,
            advanced_options=self._advanced_options,
        )

        return self._config_summary

    def get_config_summary(self) -> ConfigSummary | None:
        """Get current configuration summary.

        Returns:
            Configuration summary or None
        """
        return self._config_summary

    def get_advanced_options(self) -> AdvancedOptions:
        """Get advanced options.

        Returns:
            Advanced options
        """
        return self._advanced_options

    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate configuration.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if not self._config_summary:
            errors.append("Configuration summary is missing")
            return False, errors

        # Validate required fields
        if not self._config_summary.user_id:
            errors.append("User ID is required")

        if not self._config_summary.selected_homes:
            errors.append("At least one home must be selected")

        if self._config_summary.total_devices <= 0:
            errors.append("No devices found in selected homes")

        # Check network connectivity
        if self._network_detector:
            summary = self._network_detector.get_detection_summary()
            if "0/" in summary:
                errors.append("Network connectivity issues detected")

        return len(errors) == 0, errors


class HomeSelector:
    """Home selection helper."""

    def __init__(self) -> None:
        """Initialize home selector."""
        self._available_homes: list[dict[str, Any]] = []
        self._selected_home_ids: set[str] = set()

    def set_available_homes(self, homes: list[dict[str, Any]]) -> None:
        """Set available homes.

        Args:
            homes: List of home dictionaries
        """
        self._available_homes = homes

    def select_homes(self, home_ids: list[str]) -> None:
        """Select homes by IDs.

        Args:
            home_ids: List of home IDs to select
        """
        valid_ids = {
            home.get("homeId")
            for home in self._available_homes
            if home.get("homeId") in home_ids
        }
        self._selected_home_ids = valid_ids

    def get_selected_homes(self) -> list[dict[str, Any]]:
        """Get selected homes.

        Returns:
            List of selected home dictionaries
        """
        return [
            home
            for home in self._available_homes
            if home.get("homeId") in self._selected_home_ids
        ]

    def get_all_home_ids(self) -> set[str]:
        """Get all available home IDs.

        Returns:
            Set of home IDs
        """
        return {home.get("homeId") for home in self._available_homes}

    def count_devices_in_homes(self) -> int:
        """Count total devices in selected homes.

        Returns:
            Total device count
        """
        return sum(home.get("deviceCount", 0) for home in self.get_selected_homes())
