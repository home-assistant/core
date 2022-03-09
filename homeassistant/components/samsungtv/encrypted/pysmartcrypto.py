"""SamsungTV Encrypted."""
# flake8: noqa
# mypy: ignore-errors
# pylint: disable=[invalid-name,missing-class-docstring,missing-function-docstring,redefined-builtin,unused-variable]
import re
import sys

import requests

from . import crypto


class PySmartCrypto:
    UserId = "654321"
    AppId = "12345"
    deviceId = "7e509404-9d7c-46b4-8f6a-e2a9668ad184"

    def getFullUrl(self, urlPath):
        return "http://" + self._host + ":" + self._port + urlPath

    def GetFullRequestUri(self, step, appId, deviceId):
        return self.getFullUrl(
            "/ws/pairing?step="
            + str(step)
            + "&app_id="
            + appId
            + "&device_id="
            + deviceId
        )

    def ShowPinPageOnTv(self):
        requests.post(self.getFullUrl("/ws/apps/CloudPINPage"), "pin4")

    def CheckPinPageOnTv(self):
        full_url = self.getFullUrl("/ws/apps/CloudPINPage")
        page = requests.get(full_url).text
        output = re.search("state>([^<>]*)</state>", page, flags=re.IGNORECASE)
        if output is not None:
            state = output.group(1)
            print("Current state: " + state)
            if state == "stopped":
                return True
        return False

    def FirstStepOfPairing(self):
        firstStepURL = self.GetFullRequestUri(0, self.AppId, self.deviceId) + "&type=1"
        firstStepResponse = requests.get(firstStepURL).text

    def StartPairing(self):
        self._lastRequestId = 0
        if self.CheckPinPageOnTv():
            print("Pin NOT on TV")
            self.ShowPinPageOnTv()
        else:
            print("Pin ON TV")

    def HelloExchange(self, pin):
        hello_output = crypto.generateServerHello(self.UserId, pin)
        if not hello_output:
            return False
        content = (
            '{"auth_Data":{"auth_type":"SPC","GeneratorServerHello":"'
            + hello_output["serverHello"].hex().upper()
            + '"}}'
        )
        secondStepURL = self.GetFullRequestUri(1, self.AppId, self.deviceId)
        secondStepResponse = requests.post(secondStepURL, content).text
        print("secondStepResponse: " + secondStepResponse)
        output = re.search(
            r"request_id.*?(\d).*?GeneratorClientHello.*?:.*?(\d[0-9a-zA-Z]*)",
            secondStepResponse,
            flags=re.IGNORECASE,
        )
        if output is None:
            return False
        requestId = output.group(1)
        clientHello = output.group(2)
        lastRequestId = int(requestId)
        return crypto.parseClientHello(
            clientHello, hello_output["hash"], hello_output["AES_key"], self.UserId
        )

    def AcknowledgeExchange(self, SKPrime):
        serverAckMessage = crypto.generateServerAcknowledge(SKPrime)
        content = (
            '{"auth_Data":{"auth_type":"SPC","request_id":"'
            + str(self._lastRequestId)
            + '","ServerAckMsg":"'
            + serverAckMessage
            + '"}}'
        )
        thirdStepURL = self.GetFullRequestUri(2, self.AppId, self.deviceId)
        thirdStepResponse = requests.post(thirdStepURL, content).text
        if "secure-mode" in thirdStepResponse:
            print("TODO: Implement handling of encryption flag!!!!")
            sys.exit(-1)
        output = re.search(
            r"ClientAckMsg.*?:.*?(\d[0-9a-zA-Z]*).*?session_id.*?(\d)",
            thirdStepResponse,
            flags=re.IGNORECASE,
        )
        if output is None:
            print("Unable to get session_id and/or ClientAckMsg!!!")
            sys.exit(-1)
        clientAck = output.group(1)
        if not crypto.parseClientAcknowledge(clientAck, SKPrime):
            print("Parse client ac message failed.")
            sys.exit(-1)
        sessionId = output.group(2)
        print("sessionId: " + sessionId)
        return sessionId

    def ClosePinPageOnTv(self):
        full_url = self.getFullUrl("/ws/apps/CloudPINPage/run")
        requests.delete(full_url)
        return False

    def __init__(self, host, port, token=None, sessionid=None):
        self._lastRequestId = 0

        self._host = host
        self._port = port

        if token is None and sessionid is None:
            self.StartPairing()
            token = False
            SKPrime = False
            while not token:
                tvPIN = input("Please enter pin from tv: ")
                print("Got pin: '" + tvPIN + "'\n")
                self.FirstStepOfPairing()
                output = self.HelloExchange(tvPIN)
                if output:
                    token = output["ctx"].hex()
                    SKPrime = output["SKPrime"]
                    print("ctx: " + token)
                    print("Pin accepted :)\n")
                else:
                    print("Pin incorrect. Please try again...\n")

            sessionid = self.AcknowledgeExchange(SKPrime)
            print("SessionID: " + str(sessionid))
            self.ClosePinPageOnTv()
            print("Authorization successful :)\n")

        self._token = token
        self._sessionid = sessionid
