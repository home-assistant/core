from pyVoIP.VoIP import VoIPPhone, InvalidStateError, CallState



class sip_device():
    def __init__(self) -> None:
        self._state = "idle"
        self.phone=VoIPPhone(server="dlavrantonisserver.duckdns.org", port=5060,username= "User3", password="1234", 
                    call_callback=self.call_state,bind_ip="192.168.30.87")
        self.phone.start()

    def __del__(self):
        print('Destructor called')  
        self.phone.stop()

    def call_state(self,call):
        try:
            print("call_state")

            if call.state == CallState.RINGING:
                self._state="ringing"
                print("send push notification")
            else:
                self._state="idle"
                print("return to idle")


        except InvalidStateError:
            print("errrr")
            pass


