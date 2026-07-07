"""Two-HA spike rig: builds a main + sandbox pair bridged by a chosen option.

Hides the boilerplate so the test/benchmark module can write::

    rig = await SpikeRig.build(option="A", count=100)
    await rig.turn_on_area("spike_area")

…and observe both sandbox lights and main proxies updating.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.setup import async_setup_component

from .bridge_a import OptionALightProxy, OptionAMainBridge, OptionASandboxBridge
from .bridge_b import OptionBLightProxy, OptionBMainBridge, OptionBSandboxBridge
from .synthetic_light import SyntheticLight
from .transport import InProcessTransport

Option = Literal["A", "B"]
ENTITY_ID_PREFIX = "light.spike_light_"
AREA_ID = "spike_area"


@dataclass
class SpikeRig:
    """Holds every moving part of a spike measurement."""

    option: Option
    main_hass: HomeAssistant
    sandbox_hass: HomeAssistant
    transport: InProcessTransport
    sandbox_lights: list[SyntheticLight]
    main_proxies: list[Any] = field(default_factory=list)

    @classmethod
    async def build(
        cls,
        option: Option,
        count: int,
        *,
        main_hass: HomeAssistant,
        sandbox_hass: HomeAssistant,
    ) -> SpikeRig:
        """Set up sandbox + main + bridge + ``count`` synthetic lights."""
        # 1. Sandbox: set up light platform and N synthetic lights.
        await async_setup_component(sandbox_hass, "light", {"light": []})
        sandbox_component: EntityComponent[Any] = sandbox_hass.data["light"]
        sandbox_lights = [
            SyntheticLight(f"spike_{i}", f"Spike Light {i}") for i in range(count)
        ]
        await sandbox_component.async_add_entities(sandbox_lights)

        # 2. Transport + bridge.
        transport = InProcessTransport()
        if option == "A":
            sandbox_bridge_a = OptionASandboxBridge(sandbox_hass, transport)
            for light in sandbox_lights:
                sandbox_bridge_a.register(light)
            main_bridge: Any = OptionAMainBridge(transport)
        else:
            OptionBSandboxBridge(sandbox_hass, transport)
            main_bridge = OptionBMainBridge(transport)
        await transport.start()

        # 3. Main: set up light platform and N proxy entities.
        await async_setup_component(main_hass, "light", {"light": []})
        main_component: EntityComponent[Any] = main_hass.data["light"]
        if option == "A":
            proxies: list[Any] = [
                OptionALightProxy(
                    f"main_spike_{i}",
                    f"Spike Light {i}",
                    sandbox_entity_id=f"{ENTITY_ID_PREFIX}{i}",
                    bridge=main_bridge,
                )
                for i in range(count)
            ]
        else:
            proxies = [
                OptionBLightProxy(
                    f"main_spike_{i}",
                    f"Spike Light {i}",
                    sandbox_entity_id=f"{ENTITY_ID_PREFIX}{i}",
                    bridge=main_bridge,
                )
                for i in range(count)
            ]
        await main_component.async_add_entities(proxies)

        # 4. Area registry on main, assign each proxy entity to the spike area.
        area_reg = ar.async_get(main_hass)
        area = area_reg.async_get_or_create("Spike Area")
        entity_reg = er.async_get(main_hass)
        for proxy in proxies:
            assert proxy.entity_id is not None
            entity_reg.async_update_entity(proxy.entity_id, area_id=area.id)

        rig = cls(
            option=option,
            main_hass=main_hass,
            sandbox_hass=sandbox_hass,
            transport=transport,
            sandbox_lights=sandbox_lights,
            main_proxies=proxies,
        )
        rig._area_id = area.id  # type: ignore[attr-defined]
        return rig

    @property
    def area_id(self) -> str:
        """Return the area id main proxies are bound to."""
        return self._area_id  # type: ignore[attr-defined]

    @property
    def proxy_entity_ids(self) -> list[str]:
        """Return the entity ids of the main-side proxies."""
        return [p.entity_id for p in self.main_proxies if p.entity_id]

    async def turn_on_area(self) -> None:
        """Call ``light.turn_on`` on main targeting the spike area."""
        await self.main_hass.services.async_call(
            "light",
            "turn_on",
            {},
            target={"area_id": self.area_id},
            blocking=True,
        )

    async def turn_off_area(self) -> None:
        """Call ``light.turn_off`` on main targeting the spike area."""
        await self.main_hass.services.async_call(
            "light",
            "turn_off",
            {},
            target={"area_id": self.area_id},
            blocking=True,
        )

    async def stop(self) -> None:
        """Tear down background tasks."""
        await self.transport.stop()
