"""FRITZ camera integration.

Currently only used to display QR codes.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from .common import AvmWrapper, FritzBoxBaseEntity
from .const import DEFAULT_GUEST_WIFI_QR_REFRESH_SEC, DOMAIN, QR_CODE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a entities from a config_entry."""
    _LOGGER.debug("Setting up FRITZ!Box camera entities")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    entities = await hass.async_add_executor_job(
        _setup_guest_wifi_qr, avm_wrapper, entry.title
    )

    async_add_entities(entities, True)


def _setup_guest_wifi_qr(
    avm_wrapper: AvmWrapper, device_friendly_name: str
) -> list[FritzGuestWifiQRCamera]:
    """Set up guest wifi entity to display the qr code."""
    _LOGGER.debug("Setting up qr code camera entity")
    ssid = avm_wrapper.fritz_guest_wifi.ssid
    return [
        FritzGuestWifiQRCamera(
            avm_wrapper,
            device_friendly_name,
            ssid,
        )
    ]


class FritzGuestWifiQRCamera(FritzBoxBaseEntity, Camera):
    """Implementation of the FritzBox guest wifi QR code camera entity."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        ssid: str,
    ) -> None:
        """Initialize the camera."""
        Camera.__init__(self)

        self._attr_name = f"{device_friendly_name} {ssid} {QR_CODE}"
        self._attr_unique_id = f"{avm_wrapper.unique_id}-guest-wlan-{slugify(QR_CODE)}"
        self._attr_icon = "mdi:qrcode-scan"
        super().__init__(avm_wrapper, device_friendly_name)

        self.content_type = "image/svg+xml"
        self._ssid: str = ssid
        self._last_qr: bytes | None = None
        self._refresh_at: datetime | None = None
        self._avm_wrapper: AvmWrapper = avm_wrapper

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        if self._ssid:
            attrs["ssid"] = self._ssid
        attrs["refresh_after_seconds"] = str(DEFAULT_GUEST_WIFI_QR_REFRESH_SEC)
        return attrs

    def _needs_refresh(self) -> bool:
        """Check if a refresh of the qr code is necessary."""
        if not (self._refresh_at and self._last_qr):
            return True

        return dt_util.utcnow() > self._refresh_at

    def _generate_guest_wifi_qr(self) -> bytes:
        """Generate a QR code for the guest wifi."""
        _LOGGER.debug("start generating guest wifi qr code")
        return bytes(
            self._avm_wrapper.fritz_guest_wifi.get_wifi_qr_code("svg").getvalue()
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        if self._needs_refresh():
            _LOGGER.debug("refresh qr code")
            self._last_qr = await self.hass.async_add_executor_job(
                self._generate_guest_wifi_qr
            )
            now = dt_util.utcnow()
            self._refresh_at = now + timedelta(
                seconds=DEFAULT_GUEST_WIFI_QR_REFRESH_SEC
            )

        return self._last_qr
