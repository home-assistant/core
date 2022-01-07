import speech_recognition as sr

recognizer = sr.Recognizer()

""" recording the sound """

with sr.Microphone() as source:
    print("Adjusting noise ")
    recognizer.adjust_for_ambient_noise(source, duration=1)
    print("Recording for 4 seconds")
    recorded_audio = recognizer.listen(source, timeout=4)
    print("Done recording")

""" Recorgnizing the Audio """
try:
    print("Recognizing the text")
    text = recognizer.recognize_google(recorded_audio, language="en-IN")
    print(f"Decoded Text : {text}")

except Exception as ex:
    print(ex)
