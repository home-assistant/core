"""The YoLink Local integration models."""

from dataclasses import dataclass

from yolink.local_hub_client import YoLinkLocalHubClient

from homeassistant.config_entries import ConfigEntry

from .coordinator import YoLinkLocalCoordinator

type YoLinkLocalConfigEntry = ConfigEntry[YoLinkLocalData]


@dataclass
class YoLinkLocalData:
    """YoLink Local Data."""

    client: YoLinkLocalHubClient
    coordinators: dict[str, YoLinkLocalCoordinator]
