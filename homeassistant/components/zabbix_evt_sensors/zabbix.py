"""Zabbix helper classes."""

import contextlib
from itertools import chain
import logging

from pyzabbix.api import ZabbixAPI
import urllib3

urllib3.disable_warnings()

_LOGGER = logging.getLogger(__name__)


class ZbxEvent:
    """ZbcEvent Class."""

    def __init__(self, eid, zabbix_host, name, severity) -> None:
        """Initialize the class."""
        self.eid = eid
        self.host = zabbix_host
        self.name = name
        self.severity = severity

    def __eq__(self, other):
        """Check for equality."""
        return (
            (self.eid == other.eid)
            and (self.host == other.host)
            and (self.name == other.name)
            and (self.severity == other.severity)
        )

    def __str__(self):
        """Represent string."""
        return f"{self.host}: {self.name} ({self.severity})"

    def __repr__(self):
        """Representation."""
        return f"<ZbxEvent: {self.eid},{self.host},{self.name},{self.severity}>"


class Zbx:
    """Zbx Class."""

    def __init__(
        self, zabbix_host, zabbix_api_token, path="", port=443, ssl=True
    ) -> None:
        """Initialize the class."""
        self.host = zabbix_host
        self.api_token = zabbix_api_token
        self.path = path
        self.port = port
        self.ssl = ssl
        self.protocol = "https" if self.ssl else "http"
        self.url = f"{self.protocol}://{self.host}:{self.port}/{self.path}"
        self.zapi = ZabbixAPI(self.url)
        self.zapi.session.verify = False
        self.zapi.login(api_token=self.api_token)
        self.version = getattr(self.zapi.version, "public")

    def _get_problems(self):
        """Get Zabbix problems."""
        problems = {}
        raw_problems = self.zapi.problem.get(
            output=["eventid"], selectTags=["tag", "value"]
        )
        for problem in raw_problems:
            taglist = [f'{tag["tag"]}:{tag["value"]}' for tag in problem["tags"]]
            for tag in taglist:
                if tag not in problems:
                    problems[tag] = []
                problems[tag] = [problem["eventid"]]
        return problems

    def _get_svcs(self):
        """Get Zabbix service status."""
        svcs = {}
        raw_svcs = self.zapi.service.get(
            output=["name"], selectParents="extend", selectProblemEvents=["eventid"]
        )
        # get top level services
        raw_svcs = [service for service in raw_svcs if service["parents"] == []]
        for svc in raw_svcs:
            svcs[svc["name"]] = [prob["eventid"] for prob in svc["problem_events"]]
        return svcs

    def _get_eidmap(self, eids):
        """Map eids to ZbxEvents."""
        eidmap = {}
        raw_events = self.zapi.event.get(
            eventids=eids, output=["eventid", "name", "severity"], selectHosts=["name"]
        )
        for event in raw_events:
            with contextlib.suppress(IndexError):
                eidmap[event["eventid"]] = ZbxEvent(
                    event["eventid"],
                    event["hosts"][0]["name"],
                    event["name"],
                    event["severity"],
                )

        return eidmap

    def _output(self, data_dict):
        """Output data."""
        eids = list(chain.from_iterable(data_dict.values()))
        eidmap = self._get_eidmap(eids)
        result = {}
        for key, values in data_dict.items():
            result[key] = [eidmap[eid] for eid in values]
        return result

    def problems(self):
        """Output zabbix problems."""
        return self._output(self._get_problems())

    def services(self):
        """Output zabbix services."""
        return self._output(self._get_svcs())


if __name__ == "__main__":
    host = input("Zabbix Host: ")
    api_token = input("Zabbix API Token: ")
    z = Zbx(host, api_token)
    _LOGGER.warning("Zabbix Version: %s", z.version)
    _LOGGER.warning("Zabbix Problems: %s", z.problems())
    _LOGGER.warning("Zabbix Services: %s", z.services())
