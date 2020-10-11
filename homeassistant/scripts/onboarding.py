"""Script to programmatically perform onboarding."""
import argparse
import asyncio
import os
from typing import Dict, List

from homeassistant import runner
from homeassistant.auth import auth_manager_from_config
from homeassistant.auth.providers.homeassistant import HassAuthProvider
from homeassistant.components.onboarding import (
    STORAGE_KEY,
    STORAGE_VERSION,
    OnboadingStorage,
)
from homeassistant.components.onboarding.const import STEP_USER, STEPS
from homeassistant.config import get_default_config_dir
from homeassistant.core import HomeAssistant


def run(args: List) -> int:
    """Handle Home Assistant onboarding script."""
    parser = argparse.ArgumentParser(description="Perform Home Assistant onboarding")

    parser.add_argument(
        "-c",
        "--config",
        default=get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration",
    )
    parser.add_argument("--script", choices=["onboarding"])

    asyncio.set_event_loop_policy(runner.HassEventLoopPolicy(False))
    asyncio.run(run_command(parser.parse_args(args)))

    return 0


async def run_command(args: argparse.Namespace) -> None:
    """Run the command."""
    hass = HomeAssistant()
    hass.config.config_dir = os.path.join(os.getcwd(), args.config)
    store = OnboadingStorage(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
    data = await store.async_load()

    if data is None or not isinstance(data, Dict):
        data = {"done": []}

    if not await check_has_owner(hass, data):
        print("No user found.")
        print("Onboarding aborted!")
    else:
        for step in STEPS:
            if step not in data["done"]:
                data["done"].append(step)
        await store.async_save(data)
        print("Onboarding complete.")

    await hass.async_stop()


async def check_has_owner(hass: HomeAssistant, data: Dict) -> bool:
    """Check if there a user account is registered."""
    if STEP_USER in data["done"]:
        return True

    hass.auth = await auth_manager_from_config(hass, [{"type": "homeassistant"}], [])
    provider = hass.auth.auth_providers[0]
    if not isinstance(provider, HassAuthProvider):
        return False
    await provider.async_initialize()

    if provider.data and provider.data.users and len(provider.data.users):
        return True
    return False
