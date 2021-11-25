"""Emulation of Legrand RFLC LC7001."""
import asyncio
from typing import Final

from homeassistant.components.legrand_rflc.const import DOMAIN
from homeassistant.const import CONF_AUTHENTICATION, CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


class Server:
    """Emulated LC7001 Server for serving a matching config entry."""

    HOST: Final = "127.0.0.1"  # do not depend on "localhost" name resolution
    ADDRESS: Final = "127.0.0.1"
    MAC = "0026EC000000"

    # https://static.developer.legrand.com/files/2021/03/LC7001-AU7000-Security-Addendum-RevB.pdf
    # 7.3
    PASSWORD: Final = "MyNewPassword234"
    AUTHENTICATION: Final = "601CEF6593132D073B100830863E4DE2"
    AUTHENTICATION_OLD: Final = "D41D8CD98F00B204E9800998ECF8427E"

    SECURITY_NON_COMPLIANT: Final = b'{"MAC":"0026EC000000"}{"ID":0,"Service":"ping","CurrentTime":1626452977,"PingSeq":1,"Status":"Success"}\x00'

    SECURITY_HELLO_AUTHENTICATION_OK: Final = [
        b"Hello V1 \x009158E315149BEF9F2179D79C58F0F422 0026EC000000",
        b"3437872f1912fe9fb06ddf50eb5bf535",
        b"[OK]\n\r\n\x00",
    ]
    SECURITY_HELLO_AUTHENTICATION_INVALID: Final = [
        b"Hello V1 \x009158E315149BEF9F2179D79C58F0F422 0026EC000000",
        b"3437872f1912fe9fb06ddf50eb5bf535",
        b"[INVALID]\x00",
    ]

    def __init__(self, hass, sessions):
        """Each session is an alternating sequence of lines to write and lines we expect to read."""
        self._hass = hass
        self._sessions = sessions
        if 0 == len(sessions):
            raise ValueError("Server has no sessions")
        self._listener = None
        self._entry = None
        self._session = None

    async def start(self, start_client: bool = True):
        """Start serving sessions and, possibly, a client."""

        def session(reader, writer):
            async def _session(lines, last):

                # wait for completion of any previous session
                if self._session is not None:
                    await self._session
                self._session = asyncio.current_task()

                # cancel listener if we are the last session
                if last:
                    self._listener.cancel()
                    try:
                        await self._listener
                    except asyncio.CancelledError:
                        pass

                # alternate between writing and reading expected lines
                write = False
                for line in lines:
                    write ^= True
                    if write:
                        writer.write(line)
                        await writer.drain()
                    else:
                        assert line == await reader.readexactly(len(line))

                # unload our config entry if we have one and this is the last session
                if self._entry and last:
                    await self._hass.config_entries.async_unload(self._entry.entry_id)

            lines = self._sessions.pop(0)
            last = 0 == len(self._sessions)
            self._hass.async_create_task(_session(lines, last))

        # start emulated server that will listen on ephemeral port of HOST
        server = await asyncio.start_server(session, host=self.HOST)
        port = server.sockets[0].getsockname()[1]
        self._listener = self._hass.async_create_task(server.serve_forever())

        if not start_client:
            return port

        else:
            # create a mock config entry referencing emulated server
            self._entry = entry = MockConfigEntry(
                domain=DOMAIN,
                unique_id=self.MAC.lower(),
                data={
                    CONF_AUTHENTICATION: self.AUTHENTICATION,
                    CONF_HOST: self.HOST,
                    CONF_PORT: port,
                },
            )
            entry.add_to_hass(self._hass)

            # setup config entry (this will start a client)
            self._hass.async_create_task(
                self._hass.config_entries.async_setup(entry.entry_id)
            )

            # wait until the sessions are complete
            await self._hass.async_block_till_done()
