from gtts import gTTS

mytext = "Hello fellas"

language = "en"

myobj = gTTS(text=mytext, lang=language, slow=False)

myobj.save("welcome.mp3")


import os
import pwd

os.system("mpg321 welcome.mp3")
os.remove("welcome.mp3")
