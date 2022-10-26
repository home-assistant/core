from pyVoIP.VoIP import VoIPPhone, InvalidStateError, CallState





class sip_device():
    def __init__(self,server,port,username,password,bind_ip) -> None:
        self._state = "idle"
        self.phone=VoIPPhone(server=server,port=port,username= username, password=password, 
        cancel_callback = self.cancel,call_callback=self.ringing,bind_ip=bind_ip)
        self.phone.start()
        print("VOIP started")

    def __del__(self):
        print('Destructor called')  
        self.phone.stop()

    def cancel(self):
        print("cancel")
        self._state="idle"
        print("return to idle")

    def ringing(self,call):
        try:
            print("ringing")

            if call.state == CallState.RINGING:
                self._state="ringing"
                print("send push notification")
            else:
                self._state="idle"
                print("return to idle")


        except InvalidStateError:
            print("errrr")
            pass


