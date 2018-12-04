import brottsplatskartan

b = brottsplatskartan.BrottsplatsKartan(latitude=40.713763, longitude=-74.156850)

for i in b.get_incidents():
    print(i)

