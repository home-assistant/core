"""Authentication helper classes for the Model Context Protocol integration."""

from dataclasses import dataclass
import re

import httpx
from yarl import URL

# Headers and regex for WWW-Authenticate parsing for rfc9728
WWW_AUTHENTICATE_HEADER = "WWW-Authenticate"
RESOURCE_METADATA_REGEXP = r'resource_metadata="([^"]+)"'
SCOPES_REGEXP = r'scope="([^"]+)"'


@dataclass
class AuthenticateHeader:
    """Class to hold info from the WWW-Authenticate header for supporting rfc9728."""

    resource_metadata_url: str
    scopes: list[str] | None = None

    @classmethod
    def from_header(
        cls, url: str, error_response: httpx.Response
    ) -> AuthenticateHeader | None:
        """Create AuthenticateHeader from WWW-Authenticate header."""
        if not (header := error_response.headers.get(WWW_AUTHENTICATE_HEADER)) or not (
            match := re.search(RESOURCE_METADATA_REGEXP, header)
        ):
            return None
        resource_metadata_url = str(URL(url).join(URL(match.group(1))))
        scope_match = re.search(SCOPES_REGEXP, header)
        return cls(
            resource_metadata_url=resource_metadata_url,
            scopes=scope_match.group(1).split(" ") if scope_match else None,
        )
