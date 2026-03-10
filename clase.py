from modulo import TPI

p=7
o="j"
t=False
k=False
if False:
    print("Hola")
elif t:
    print("none")
else: 
    print("yy")

Monte=["pasto", "Sierra", "Nevada"] 
Monte.append ("Santa Marta")
print(Monte[3])

Nombres=("Angel", "Juan", "Daniela")
print(Nombres[0])

edad={"Angel":24, "Daniela":21}
print(edad["Angel"])
Ventana=3
Contador=0


# while Contador<Ventana:
#     print(Contador)
#     Contador=Contador+1 #Suma 1
    
for elemento in edad:
    print(edad[elemento])



print(TPI(85, 96))
print(__name__)



