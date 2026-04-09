import logging
from .notificationdevice import effortlesshomenotificationdevice
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    devices = []
    stored = hass.data.get("effortlesshome_notify_devices", {})

    _LOGGER.info("[EffortlessHome] In setup notify")

    for device_id, data in stored.items():
        devices.append(
            effortlesshomenotificationdevice(
                hass,
                entry,
                device_id=device_id,
                name=data.get("name", f"Device {device_id}"),
                person_email=data.get("person_email"),
            )
        )

    async_add_entities(devices, True)
