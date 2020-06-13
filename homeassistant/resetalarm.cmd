del /Q D:\OneDrive\toReview\1\*.*
del /Q D:\OneDrive\toReview\3\*.*
del /Q D:\OneDrive\toReview\4\*.*
del /Q D:\OneDrive\toReview\5\*.*
del /Q D:\OneDrive\toReview\7\*.*
del /Q D:\OneDrive\toReview\10\*.*
del /Q D:\OneDrive\toReview\11\*.*
del /Q D:\OneDrive\toReview\12\*.*
del /Q D:\OneDrive\toReview\13\*.*
del /Q D:\OneDrive\toReview\14\*.*
del /Q D:\OneDrive\toReview\16\*.*
del /Q D:\OneDrive\toReview\17\*.*
del /Q C:\inetpub\wwwroot\motion.html
del /Q C:\inetpub\wwwroot\videos\*.*

copy C:\inetpub\wwwroot\motionEmpty.html C:\inetpub\wwwroot\motion.html
python AlarmStatusChanger.py -a clear