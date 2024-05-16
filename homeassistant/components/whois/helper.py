"""A helper class that abstracts away the usage of external whois libraries."""

from dataclasses import dataclass
from typing import Any

import whois


@dataclass(kw_only=True)
class Domain:
    """A class internally representing a domain."""

    admin: Any = None
    creation_date: Any = None
    dnssec: Any = None
    expiration_date: Any = None
    last_updated: Any = None
    name_servers: Any = None
    owner: Any = None
    registrar: Any = None
    reseller: Any = None
    registrant: Any = None
    status: Any = None
    statuses: Any = None


class WhoisUnknownTLD(Exception):
    """Exception class when unknown TLD encountered."""


class GenericWhoisError(Exception):
    """Exception class for all other exceptions originating from the external whois library."""


def query(domain: str) -> Domain | None:
    """Wrap around the external whois library call and return internal domain representation."""

    wh = None
    try:
        wh = whois.query(domain)
    except whois.exceptions.UnknownTld as ex:
        raise WhoisUnknownTLD from ex
    except Exception as ex:
        raise GenericWhoisError from ex
    else:
        # backward-compatibility
        if wh is None:
            return None

        # field mapping here
        return Domain(
            admin=wh.admin,
            creation_date=wh.creation_date,
            dnssec=wh.dnssec,
            expiration_date=wh.expiration_date,
            last_updated=wh.last_updated,
            name_servers=wh.name_servers,
            owner=wh.owner,
            registrar=wh.registrar,
            reseller=wh.reseller,
            registrant=wh.registrant,
            status=wh.status,
            statuses=wh.statuses,
        )
