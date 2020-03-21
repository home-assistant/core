from sys import argv

from bravia_tv import BraviaRC

host = argv[1]
pin = argv[2]
braviarc = BraviaRC(host)
braviarc.connect(str(pin), "HomeAssistant", "Home Assistant")
print(braviarc.get_system_info())
