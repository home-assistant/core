import logging

from frisquet_connect.const import (
    BOOST_ORDER_LABEL,
    EXEMPTION_ORDER_LABEL,
    SANITARY_WATER_ORDER_LABEL,
    SELECTOR_ORDER_LABEL,
    SanitaryWaterMode,
    ZoneMode,
    ZoneModeLabelOrder,
    ZoneSelector,
)
from frisquet_connect.domains.authentication.authentication_request import (
    AuthenticationRequest,
)
from frisquet_connect.domains.authentication.authentication import (
    Authentication,
)
from frisquet_connect.domains.consumption.consumption_site import ConsumptionSite
from frisquet_connect.domains.site.site import Site
from frisquet_connect.repositories.core_repository import (
    async_do_get,
    async_do_post,
    async_do_websocket,
)
from frisquet_connect.utils import log_methods


FRISQUET_CONNECT_WEBSOCKET_URL = "wss://fcappcom.frisquet.com/"

FRISQUET_CONNECT_API_URL = "https://fcutappli.frisquet.com"

AUTH_ENDPOINT = f"{FRISQUET_CONNECT_API_URL}/api/v1/authentifications"

SITES_ENDPOINT = f"{FRISQUET_CONNECT_API_URL}/api/v1/sites"
SITES_CONSO_ENDPOINT = "{site_url}/conso"

ORDER_ENDPOINT = f"{FRISQUET_CONNECT_API_URL}/api/v1/ordres"


LOGGER = logging.getLogger(__name__)


@log_methods
class FrisquetConnectRepository:

    async def async_get_token_and_sites(
        self, email: str, password: str
    ) -> Authentication:
        payload = AuthenticationRequest(email, password).to_dict()
        response_json = await async_do_post(AUTH_ENDPOINT, None, payload)
        return Authentication(response_json)

    async def async_get_site_info(self, site_id: str, token: str) -> Site:
        params = {"token": token}
        response_json = await async_do_get(f"{SITES_ENDPOINT}/{site_id}", params)
        return Site(response_json)

    async def async_get_site_conso(self, site_id: str, token: str) -> ConsumptionSite:
        params = {"token": token, "types[]": ["CHF", "SAN"]}
        site_url = f"{SITES_ENDPOINT}/{site_id}"
        response_json = await async_do_get(
            SITES_CONSO_ENDPOINT.format(site_url=site_url), params
        )
        return ConsumptionSite(response_json)

    async def async_set_temperature(
        self,
        site_id: str,
        zone_id: str,
        zone_mode: ZoneMode,
        temperature: int,
        token: str,
    ) -> dict:

        mode_target = ZoneModeLabelOrder[zone_mode.name].value
        key = f"{mode_target}_{zone_id}"

        payload = [{"cle": key, "valeur": temperature}]
        response_json = await self._async_do_site_action(site_id, token, payload)
        return response_json

    async def async_set_sanitary_water_mode(
        self, site_id: str, sanitary_water_mode: SanitaryWaterMode, token: str
    ) -> dict:

        payload = [
            {"cle": SANITARY_WATER_ORDER_LABEL, "valeur": sanitary_water_mode.value}
        ]
        response_json = await self._async_do_site_action(site_id, token, payload)
        return response_json

    async def async_set_selector(
        self, site_id: str, zone_id: str, zone_selector: ZoneSelector, token: str
    ) -> dict:

        key = f"{SELECTOR_ORDER_LABEL}_{zone_id}"
        selector_target = ZoneSelector[zone_selector.name].value

        payload = [{"cle": key, "valeur": selector_target}]
        response_json = await self._async_do_site_action(site_id, token, payload)
        return response_json

    async def async_set_exemption(
        self, site_id: str, zone_mode: ZoneMode, token: str
    ) -> dict:
        # TODO : Check if the preset_mode is AUTO
        if zone_mode not in [ZoneMode.COMFORT, ZoneMode.REDUCED, None]:
            error_message = f"Incompatible zone mode: {zone_mode}"
            LOGGER.error(error_message)
            raise ValueError(error_message)

        value = 0 if not zone_mode else zone_mode.value

        payload = [{"cle": EXEMPTION_ORDER_LABEL, "valeur": value}]
        response_json = await self._async_do_site_action(site_id, token, payload)
        return response_json

    async def async_set_boost(
        self, site_id: str, zone_id: str, enable: bool, token: str
    ) -> dict:
        key = f"{BOOST_ORDER_LABEL}_{zone_id}"
        value = 1 if enable else 0

        payload = [{"cle": key, "valeur": value}]
        response_json = await self._async_do_site_action(site_id, token, payload)
        return response_json

    async def _async_do_site_action(
        self, site_id: str, token: str, payload: list[dict]
    ) -> dict:
        params = {"token": token}
        response_json = await async_do_post(
            f"{ORDER_ENDPOINT}/{site_id}", params, payload
        )

        params["identifiant_chaudiere"] = site_id
        payload = {"type": "ORDRE_EN_ATTENTE"}
        await async_do_websocket(FRISQUET_CONNECT_WEBSOCKET_URL, params, payload)

        return response_json
