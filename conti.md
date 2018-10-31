print("convert an integer input by user into binary and vice versa")
print("convert in binary")
res=0
count=0
sum=0
flag=0
a=[]
y=int(input("enter the number in binary:"))
flag=y
while(flag>0):
    res=flag%10
    count=count+1
    flag=flag//10
for i in range (0,count):
    dig=(y%10)*(2**i)
    sum=sum+dig
    y=y//10
print(sum)
print("convert in integer")
y=int(input("enter the integer:"))
while(1):
    quo=y//2
    rem=y%2
    a.append(rem)
    y=quo
    if(y==0):
        break
a.sort(reverse=True)
print(a)
