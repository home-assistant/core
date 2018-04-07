"""Tests for sensor.snmp."""

import unittest
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant
from threading import Thread

from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.proto.api import v2c
from pysnmp.proto.rfc1902 import Opaque

import time

_PORT = 10161
_BASE_OID = (1, 3, 6, 1, 4, 1, 6574, 4)
_OID1 = _BASE_OID + (1, 1, 1)
_OID2 = _BASE_OID + (2, 1, 1)
_OID3 = _BASE_OID + (3, 1, 1)


class TestSnmp(unittest.TestCase):
    """Test basic functionality of sensor.snmp."""

    def setUp(self):
        """Setup a hoss instance for testing."""
        self.hass = get_test_home_assistant()
        self.hass.start()
        self.snmpEngine = None
        self._agent_thread = None

    def tearDown(self):
        """Clean up after the tests.

        Especially take care of the snmpEngine.
        """
        if self.snmpEngine is not None:
            self.snmpEngine.transportDispatcher.jobFinished(1)
            self.snmpEngine.transportDispatcher.unregisterRecvCbFun(
                recvId=None)
            self.snmpEngine.transportDispatcher.unregisterTransport(
                udp.domainName)
        if self._agent_thread is not None:
            self._agent_thread.join(0.01)
        self.hass.stop()

    def _run_agent(self):
        """Run a snmp thread so that we can get data from it.

        This is based on the examples from the pysnmp library.
        """
        self.snmpEngine = engine.SnmpEngine()
        config.addTransport(
            self.snmpEngine,
            udp.domainName,
            udp.UdpTransport().openServerMode(('127.0.0.1', _PORT))
        )
        config.addV1System(self.snmpEngine, 'my-area', 'public')
        config.addVacmUser(self.snmpEngine, 2, 'my-area', 'noAuthNoPriv',
                           _BASE_OID)
        snmpContext = context.SnmpContext(self.snmpEngine)
        mibBuilder = snmpContext.getMibInstrum().getMibBuilder()

        MibScalar, MibScalarInstance = mibBuilder.importSymbols(
            'SNMPv2-SMI', 'MibScalar', 'MibScalarInstance'
        )

        class MyStaticMibScalarInstance1(MibScalarInstance):
            # noinspection PyUnusedLocal,PyUnusedLocal
            def getValue(self, name, idx):
                return self.getSyntax().clone("test string")

        class MyStaticMibScalarInstance2(MibScalarInstance):
            # noinspection PyUnusedLocal,PyUnusedLocal
            def getValue(self, name, idx):
                return self.getSyntax().clone(1234)

        class MyStaticMibScalarInstance3(MibScalarInstance):
            # noinspection PyUnusedLocal,PyUnusedLocal
            def getValue(self, name, idx):
                return self.getSyntax().clone(
                    Opaque(value=b'\x9fx\x04=\xa4\x00\x00'))

        mibBuilder.exportSymbols(
            '__MY_MIB', MibScalar(_OID1, v2c.OctetString()),
            MyStaticMibScalarInstance1(_OID1, (0,), v2c.OctetString())
        )

        mibBuilder.exportSymbols(
            '__MY_MIB', MibScalar(_OID2, v2c.Integer()),
            MyStaticMibScalarInstance2(_OID2, (0,), v2c.Integer())
        )

        mibBuilder.exportSymbols(
            '__MY_MIB', MibScalar(_OID3, v2c.Opaque()),
            MyStaticMibScalarInstance3(_OID3, (0,), v2c.Opaque())
        )

        cmdrsp.GetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.NextCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.BulkCommandResponder(self.snmpEngine, snmpContext)
        self.snmpEngine.transportDispatcher.jobStarted(1)

        # Run I/O dispatcher which would receive queries and send responses
        try:
            self.snmpEngine.transportDispatcher.runDispatcher()
        except:
            self.snmpEngine.transportDispatcher.closeDispatcher()
            raise

    def test_read_values(self):
        """Test reading data from the sensor.snmp.

        Testing with different data types as they have different encodings.
        """
        self._agent_thread = Thread(target=self._run_agent)
        self._agent_thread.start()
        time.sleep(1)
        assert setup_component(self.hass, 'sensor', {
            'sensor': [
                {
                    'platform': 'snmp',
                    'host': '127.0.0.1',
                    'baseoid': '.'.join([str(i) for i in _OID1])+'.0',
                    'name': 'stringvar',
                    'community': 'public',
                    'port': _PORT,
                    'accept_errors': False,
                    'version': '2c',
                },
                {
                    'platform': 'snmp',
                    'host': '127.0.0.1',
                    'baseoid': '.'.join([str(i) for i in _OID2])+'.0',
                    'name': 'intvar',
                    'community': 'public',
                    'port': _PORT,
                    'accept_errors': False,
                    'version': '2c',
                },
                {
                    'platform': 'snmp',
                    'host': '127.0.0.1',
                    'baseoid': '.'.join([str(i) for i in _OID3]) + '.0',
                    'name': 'floatvar',
                    'community': 'public',
                    'port': _PORT,
                    'accept_errors': False,
                    'version': '2c',
                },
            ]
            })
        self.hass.block_till_done()

        str_state = self.hass.states.get('sensor.stringvar')
        self.assertEquals('test string', str_state.state)

        int_state = self.hass.states.get('sensor.intvar')
        self.assertEquals('1234', int_state.state)

        int_state = self.hass.states.get('sensor.floatvar')
        self.assertEquals('0.080078125', int_state.state)
