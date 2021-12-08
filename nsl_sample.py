# from gtts import gTTS
# mytext = "Welcome to geeksforgeeks!"
# language = "en"
# myobj = gTTS(text=mytext, lang=language, slow=False)
# myobj.save("welcome.wav")

# import os

# os.system("sudo aplay -r 2500 welcome.mp3")


# from playsound import playsound

# playsound("welcome.mp3")
# print("playing sound using playsound")


# from pydub import AudioSegment
# from pydub.playback import play

# song = AudioSegment.from_mp3("welcome.mp3")
# print("playing sound using pydub")
# play(song)


import pyttsx3

engine = pyttsx3.init()
engine.say("I will speak this text")
engine.runAndWait()
