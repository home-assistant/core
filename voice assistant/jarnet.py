 #from traceback import print_tb
import collections
import pyttsx3
import speech_recognition as sr
import datetime
import wikipedia
import webbrowser
import os
import smtplib
import pywhatkit
import pyjokes
import wolframalpha
# ecapture — This module is used to capture images from your camera
# subprocess _ That is used to log off the computer.
# request- The request module is used to send all types of HTTP request. Its accepts URL as parameters and gives access to the given URL’S.
# Json- The json module is used for storing and exchanging data.
# wolfram alpha — Wolfram Alpha is an API which can compute expert-level answers using Wolfram’s algorithms, knowledge base and AI technology. It is made possible by the Wolfram Language
# os — This module is a standard library in python and it provides the function to interact with operating system
# import random
# import chatbot
# import qrscan
# import Bday
# import googletrans
# import videoTester
#from wikipedia.wikipedia import languages, search.
engine = pyttsx3.init('sapi5')
voices = engine.getProperty('voices')
engine.setProperty('voice',voices[0].id)


def speak(audio):
    engine.say(audio)
    engine.runAndWait()
def wishMe():
    hour = int(datetime.datetime.now().hour)
    if hour>=0 and hour<12 :
        speak("Good Morning.")
    elif hour>=12 and hour<18 :
        speak("Good afternoon.")
    else:
        speak("Good evening")
      #  speak("I am zarnet sir . How can i help you")

def takecommand():

     r=sr.Recognizer()
     with sr.Microphone() as source :
          r.adjust_for_ambient_noise(source)
          print("Listening...")
          r.pause_threshold = 1
          audio = r.listen(source)
     try:
         print("Recognizing...")
         query = r.recognize_google(audio, language='en-in')
         print(f"user said : {query}\n")
     except Exception as e:
          print("say that again please")
          return "None"
     return query


if __name__=="__main__":
     wishMe()
     while (1):
          query = takecommand().lower()

          if 'tell me something about' in query or 'show me' in query or 'i want to know' in query:
               speak('searching wikipedia and then showing you the results sirr')
               query=query.replace("wikipedia","")
               results = wikipedia.summary(query,sentences=1)
               speak("According to wikipedia")
               print(results)
               speak(results)

          elif 'play' in query :
               song = query.replace('play','')
               speak('playing' + song)
               pywhatkit.playonyt(song)

          elif 'search' in query :
               searched = query.replace('search','')
               speak('performing the serached results sir' + searched)
               pywhatkit.search(searched)

          elif 'joke' in query :
               joke = pyjokes.get_joke()
               print(joke)
               speak(joke)

          elif 'open youtube' in query:
               webbrowser.open("youtube.com")

          elif 'solution website' in query:
               webbrowser.open("www.wolframalpha.com")
          elif 'open google' in query:
               webbrowser.open("google.com")
          elif 'solve' in query  or 'temperature' in query or 'weather' in query or 'what is' in query or 'animal' in query or 'chemistry' in query:
               site = wolframalpha.Client("UE6K2P-UY7WHL8JTT")
               try:
                    res = site.query(query)
                    print(next(res.results).text)
                    speak(next(res.results).text)
               except Exception:
                    print("There is some error sir , please fix it .")
                    speak("There is some error please fix it sir ")


          elif 'where do i live' in query:
               speak("You live in India WestBengal")
          elif 'college' in query:
               speak("You read in H I T Haldia")
          elif 'doctor strange' in query:
             movie = 'E:\\mOvIeS'
             mOvIeS = os.listdir(movie)
             # print(songs)
             os.startfile(os.path.join(movie,mOvIeS[6]))
          elif 'exit program' in query :
             exit()

          else :
               print("NO input voice sir ")
               