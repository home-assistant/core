"""Main interface for Molohub."""
from .molo_client_app import MOLO_CLIENT_APP
from .molo_client_config import MOLO_CONFIGS
from .molo_hub_client import MoloHubClient


def run_proxy(hass):
    """Run Molohub application."""
    molo_client = MoloHubClient(
        MOLO_CONFIGS.get_config_object()['server']['host'],
        int(MOLO_CONFIGS.get_config_object()['server']['port']))
    MOLO_CLIENT_APP.run_reverse_proxy(hass, molo_client)


def stop_proxy():
    """Stop Molohub application."""
    MOLO_CLIENT_APP.stop_reverse_proxy()
