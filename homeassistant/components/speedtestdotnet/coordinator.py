"""Coordinator for speedtestdotnet."""

from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Any, cast, override
from xml.etree import ElementTree

import speedtest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SERVER_ID, DEFAULT_SCAN_INTERVAL, DEFAULT_SERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)

DYNAMIC_SERVERS_URL = "://www.speedtest.net/speedtest-servers.php"

type SpeedTestConfigEntry = ConfigEntry[SpeedTestDataCoordinator]
type SpeedTestServers = dict[float, list[dict[str, Any]]]


def _normalize_server_ids(server_ids: Iterable[Any] | None) -> set[int]:
    """Normalize server IDs to integers."""
    if server_ids is None:
        return set()

    normalized_server_ids = set()
    for server_id in server_ids:
        try:
            normalized_server_ids.add(int(server_id))
        except (TypeError, ValueError) as err:
            raise speedtest.InvalidServerIDType(
                f"{server_id} is an invalid server type, must be int"
            ) from err

    return normalized_server_ids


def _read_response(response: Any) -> bytes:
    """Read an HTTP response from speedtest-cli."""
    response_chunks: list[bytes] = []
    stream: Any | None = None
    try:
        stream = speedtest.get_response_stream(response)
        while True:
            try:
                chunk = stream.read(1024)
            except (OSError, EOFError) as err:
                raise speedtest.ServersRetrievalError(err) from err
            if len(chunk) == 0:
                break
            response_chunks.append(chunk)
    finally:
        if stream is not None:
            stream.close()
        response.close()

    return b"".join(response_chunks)


def _get_dynamic_servers(
    api: speedtest.Speedtest, servers: Iterable[Any] | None = None
) -> SpeedTestServers:
    """Retrieve servers from the dynamic speedtest.net server endpoint."""
    selected_server_ids = _normalize_server_ids(servers)

    headers = {}
    if speedtest.gzip:
        headers["Accept-Encoding"] = "gzip"

    request = speedtest.build_request(
        f"{DYNAMIC_SERVERS_URL}?threads={api.config['threads']['download']}",
        headers=headers,
        secure=getattr(api, "_secure", False),
    )
    response, error = speedtest.catch_request(
        request, opener=getattr(api, "_opener", None)
    )
    if error:
        raise speedtest.ServersRetrievalError(error)
    if response is None:
        raise speedtest.ServersRetrievalError()

    servers_xml = _read_response(response)
    if int(response.code) != 200:
        raise speedtest.ServersRetrievalError()

    try:
        root = ElementTree.fromstring(servers_xml)
    except ElementTree.ParseError as err:
        raise speedtest.SpeedtestServersError(
            f"Malformed speedtest.net server list: {err}"
        ) from err

    ignore_servers = set(api.config.get("ignore_servers", []))
    dynamic_servers: SpeedTestServers = {}
    for server in root.iter("server"):
        attrib = dict(server.attrib)
        try:
            server_id = int(attrib["id"])
        except (KeyError, ValueError):
            continue

        if selected_server_ids and server_id not in selected_server_ids:
            continue
        if server_id in ignore_servers:
            continue

        try:
            distance = speedtest.distance(
                api.lat_lon,
                (float(attrib["lat"]), float(attrib["lon"])),
            )
        except (KeyError, TypeError, ValueError):
            continue

        attrib["d"] = distance
        dynamic_servers.setdefault(distance, []).append(attrib)

    if selected_server_ids and not dynamic_servers:
        raise speedtest.NoMatchedServers()

    return dynamic_servers


def _merge_servers(
    servers: SpeedTestServers, servers_to_merge: SpeedTestServers
) -> None:
    """Merge additional servers into a speedtest-cli server list."""
    known_server_ids = {
        str(server.get("id"))
        for server_list in servers.values()
        for server in server_list
    }

    for distance, server_list in servers_to_merge.items():
        target_server_list = servers.setdefault(distance, [])
        for server in server_list:
            server_id = str(server.get("id"))
            if server_id in known_server_ids:
                continue
            target_server_list.append(server)
            known_server_ids.add(server_id)


def _filter_servers_by_id(
    servers: SpeedTestServers, server_id: Any
) -> SpeedTestServers:
    """Filter a speedtest-cli server list to one server ID."""
    selected_server_ids = _normalize_server_ids([server_id])
    matching_servers: SpeedTestServers = {}

    for distance, server_list in servers.items():
        for server in server_list:
            try:
                if int(server["id"]) not in selected_server_ids:
                    continue
            except (KeyError, TypeError, ValueError):
                continue

            matching_servers.setdefault(distance, []).append(server)

    if not matching_servers:
        raise speedtest.NoMatchedServers()

    return matching_servers


class SpeedTestDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Get the latest data from speedtest.net."""

    config_entry: SpeedTestConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SpeedTestConfigEntry,
        api: speedtest.Speedtest,
    ) -> None:
        """Initialize the data object."""
        self.api = api
        self.servers: dict[str, dict] = {DEFAULT_SERVER: {}}
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )

    def update_servers(self) -> None:
        """Update list of test servers."""
        test_servers = self.api.get_servers()
        try:
            _merge_servers(test_servers, _get_dynamic_servers(self.api))
        except speedtest.SpeedtestException as err:
            _LOGGER.debug(
                "Unable to retrieve dynamic speedtest.net server list: %s", err
            )
        self.api.servers = test_servers

        test_servers_list = [
            server for servers in test_servers.values() for server in servers
        ]
        for server in sorted(
            test_servers_list,
            key=lambda server: (
                server["country"],
                server["name"],
                server["sponsor"],
            ),
        ):
            self.servers[
                f"{server['country']} - {server['sponsor']} - {server['name']}"
            ] = server

    def update_data(self) -> dict[str, Any]:
        """Get the latest data from speedtest.net."""
        self.update_servers()
        self.api.closest.clear()
        if server_id := self.config_entry.options.get(CONF_SERVER_ID):
            try:
                self.api.servers = _filter_servers_by_id(self.api.servers, server_id)
            except speedtest.NoMatchedServers:
                self.api.servers = _get_dynamic_servers(self.api, servers=[server_id])

        best_server = self.api.get_best_server()
        _LOGGER.debug(
            "Executing speedtest.net speed test with server_id: %s",
            best_server["id"],
        )
        self.api.download()
        self.api.upload()
        return cast(dict[str, Any], self.api.results.dict())

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update Speedtest data."""
        try:
            return await self.hass.async_add_executor_job(self.update_data)
        except speedtest.NoMatchedServers as err:
            raise UpdateFailed("Selected server is not found.") from err
        except speedtest.SpeedtestException as err:
            raise UpdateFailed(err) from err
