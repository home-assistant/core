from http import server

API_GET = b'{"aircons":{"ac1":{"info":{"climateControlModeIsRunning":false,"countDownToOff":0,"countDownToOn":0,"fan":"high","filterCleanStatus":0,"freshAirStatus":"none","mode":"vent","myZone":0,"name":"AC","setTemp":24,"state":"off"},"zones":{"z01":{"error":0,"maxDamper":100,"measuredTemp":0,"minDamper":0,"motion":0,"motionConfig":1,"name":"Zone 1","number":1,"rssi":0,"setTemp":24,"state":"open","type":0,"value":100}}}},"system":{"hasAircons":true,"hasLights":false,"hasSensors":false,"hasThings":false,"hasThingsBOG":false,"hasThingsLight":false,"name":"e-zone","rid":"uniqueid","sysType":"e-zone","tspModel":"tspnumbers"}}'
API_SET = b'{"ack":true,"request":"setAircon"}'


class AdvantageAirHandler(server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        if self.path == "/getSystemData":
            self.wfile.write(API_GET)
        else:
            self.wfile.write(API_SET)


class AdvantageAirEmulator:
    def __init__(self, port=2025):
        self.httpserver = server.HTTPServer(("", port), AdvantageAirHandler)
        self.httpserver.serve_forever()

    def stop(self):
        self.httpserver.socket.close()
