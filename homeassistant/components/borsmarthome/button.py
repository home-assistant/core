"""Ave tapparella."""

import logging
from urllib.parse import urlparse

import paramiko

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HubConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add buttons for passed config_entry in HA."""
    # The hub is loaded from the associated entry runtime data that was set in the
    # __init__.async_setup_entry function
    hub = config_entry.runtime_data

    ave_wbs = DeviceInfo(
        identifiers={
            # Serial numbers are unique identifiers within a specific domain
            (COVER_DOMAIN, hub.hub_id)
        },
        name="Web Server",
        manufacturer="AVE",
        model="AVE WebServer",
        model_id="53AB-WBS",
    )

    parsed_url = urlparse(hub.host)
    host = parsed_url.hostname

    async_add_entities(
        [
            RestartApiServerButtonEntity(ave_wbs, host),
            RestartDpServerButtonEntity(ave_wbs, host),
            BootstartButtonEntity(ave_wbs, host),
            RebootButtonEntity(ave_wbs, host),
        ]
    )


class RestartButtonEntity(ButtonEntity):
    """Ave webserver restart button entity in ha."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, device_info: DeviceInfo, name: str, host: str) -> None:
        """Initialize the entity."""
        self._attr_device_info = device_info
        self._attr_name = name
        self._host = host
        self.unique_id = f"avebus_restart_{name}"

    def send_ssh_command(self, command: str) -> None:
        """Send command to the host."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self._host, username="root", password="temppwd")
        ssh.exec_command(command)
        ssh.close()


class RestartApiServerButtonEntity(RestartButtonEntity):
    """Ave webserver restart api server button entity in ha."""

    def __init__(self, device_info: DeviceInfo, host: str) -> None:
        """Initialize the entity."""
        super().__init__(device_info, "Restart API server", host)

    def press(self) -> None:
        """Send command to restart the api server."""
        super().send_ssh_command("/usr/local/dominaplus/launcher/start_dpapiserver.sh")


class RestartDpServerButtonEntity(RestartButtonEntity):
    """Ave webserver restart server button entity in ha."""

    def __init__(self, device_info: DeviceInfo, host: str) -> None:
        """Initialize the entity."""
        super().__init__(device_info, "Restart Domina server", host)

    def press(self) -> None:
        """Send command to restart the DP server."""
        super().send_ssh_command("/usr/local/dominaplus/launcher/start_dpserver.sh")


class BootstartButtonEntity(RestartButtonEntity):
    """Ave webserver restart all button entity in ha."""

    def __init__(self, device_info: DeviceInfo, host: str) -> None:
        """Initialize the entity."""
        super().__init__(device_info, "Restart bootstart", host)

    def press(self) -> None:
        """Send command to restart bootstart."""
        super().send_ssh_command("/usr/local/dominaplus/launcher/bootstart.sh")


class RebootButtonEntity(RestartButtonEntity):
    """Ave webserver reboot button entity in ha."""

    def __init__(self, device_info: DeviceInfo, host: str) -> None:
        """Initialize the entity."""
        super().__init__(device_info, "Reboot", host)

    def press(self) -> None:
        """Send command to reboot."""
        super().send_ssh_command("shutdown -r now")
