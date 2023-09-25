import sqlite3    
import datetime 
import msvcrt
from progress.bar import Bar
from colorama import Fore,just_fix_windows_console

just_fix_windows_console()

print("")
rango_de_fecha_inicio = input( Fore.GREEN + "Introduzca la fecha inicio con el formato YYYY/MM/DD-HH/MM/SS: " + Fore.RESET  )
rango_de_fecha_final  = input( Fore.GREEN + "Introduzca la fecha final con el formato  YYYY/MM/DD-HH/MM/SS: " + Fore.RESET  )
nombre_ddbb  = input( Fore.GREEN + "Introduzca el nombre del archivo de la base de datos " + Fore.RESET  )
print("")

# Para pruebas
#nombre_ddbb = "weewx.sdb.old"
#rango_de_fecha_inicio = "2000-01-01 00:00:00"
#rango_de_fecha_final = "2025-01-01 00:00:00"

   

# Pasa las fechas a epoch
epoch_inicio = int(datetime.datetime(int(rango_de_fecha_inicio[0:4]), (int(rango_de_fecha_inicio[5:7])), (int(rango_de_fecha_inicio[8:10])), (int(rango_de_fecha_inicio[11:13])), (int(rango_de_fecha_inicio[14:16])), (int(rango_de_fecha_inicio[17:19]))).timestamp())
epoch_final  = int(datetime.datetime(int(rango_de_fecha_final[0:4]), (int(rango_de_fecha_final[5:7])), (int(rango_de_fecha_final[8:10])), (int(rango_de_fecha_final[11:13])), (int(rango_de_fecha_final[14:16])), (int(rango_de_fecha_final[17:19]))).timestamp())

if epoch_final < epoch_inicio:
    print( Fore.RED + "La fecha de inicio no puede ser posterior a la fecha final"   )
    print(  "Pulse intro para salir "  + Fore.RESET  )
    msvcrt.getch()
    exit()

# Creando una lista de alertas accediendo a la base de datos de las alertas
epoch_and_rain = []

try:
    conexion=sqlite3.connect(nombre_ddbb) 
    cursor=conexion.execute("select dateTime,rain,rainRate from archive")
except:
    print(  Fore.RED +  "No se ha podido hallar el archivo, recuerde colocar el archivo de la base de datos en la misma carpeta de la aplicación y escriba su nombre de nuevo"   )
    print(  "Pulse intro para salir "  + Fore.RESET   )
    msvcrt.getch()
    exit()

for registro_estacion in cursor:
    epoch_time = registro_estacion[0]
    rain_inch = registro_estacion[1]
    rain_rate_inch = registro_estacion[2]
   
    if epoch_time > epoch_inicio and epoch_time < epoch_final:

        if rain_inch:
            rain_mm = float(rain_inch)*25.4
            rain_rate_mm = float(rain_rate_inch)*25.4

            if epoch_time:
                epoch_and_rain.append((epoch_time,rain_mm,rain_rate_mm))

conexion.close()


# Mostrando precipitación acumulada en el periodo
totalrain = 0.0
for data in epoch_and_rain:
    rain = data[1]
    totalrain = totalrain + rain

print( Fore.CYAN + "La precipitación acumulada en el periodo de tiempo seleccionado es de: " + Fore.YELLOW + str(round(totalrain,2)) + " mm" + Fore.RESET  )
print("")


# Corrección del valor
siono  = input( Fore.GREEN + "¿Desea modificar la precipitación total del periodo seleccionado? " + Fore.RESET  )
print("")

if siono == "si" or siono == "Si" or siono == "SI":
    # Reemplaza , por . para convertir a float
    nuevo_total_rain = str(input( Fore.GREEN + "Introduzca nuevo valor en milímetros: " + Fore.RESET ))
    print("")
    if "," in nuevo_total_rain:
        nuevo_total_rain = nuevo_total_rain.replace(",",".")
    nuevo_total_rain = float(nuevo_total_rain)
    # Extrae la desviación para aplicar como factor de corrección y el porcentaje de desviación
    desviacion = nuevo_total_rain/totalrain
    porcentaje_desviación = (1/(1/desviacion))*100

    print( Fore.GREEN + "El valor introducido es el " +Fore.YELLOW+ str(round(porcentaje_desviación,2)) + "%" + Fore.GREEN + " respecto al valor de la estación" + Fore.RESET)
    siono = input( Fore.MAGENTA + "¿Esta seguro de modificar el valor de " + Fore.YELLOW + str(round(totalrain,2)) + "mm" + Fore.MAGENTA + " por el de " +  Fore.YELLOW + str(nuevo_total_rain) + "mm" +  Fore.MAGENTA + " para el periodo transcurrido entre el " + Fore.YELLOW +   str(rango_de_fecha_inicio) + Fore.MAGENTA +  " y el " + Fore.YELLOW +  str(rango_de_fecha_final) + Fore.MAGENTA +  "? " + Fore.RESET  )
    print("")

    if siono == "si" or siono == "Si" or siono == "SI":
       
        print(Fore.GREEN + "Esta operación puede tardar unos minutos, por favor espere..." + Fore.RESET)
        longitud_progress_bar = len(epoch_and_rain)
        bar1 = Bar('Procesando:', max=longitud_progress_bar)
        for data in epoch_and_rain:

            original_rain = data[1]
            original_rain_rate = data[2]
            new_rain = desviacion * ((original_rain)/25.4)
            new_rain_rate = desviacion * ((original_rain_rate)/25.4)

            bar1.next()

            conexion=sqlite3.connect(nombre_ddbb) 
            cursor=conexion.execute("select dateTime,rain,rainRate from archive")
            cursor.execute("UPDATE archive set rain=? WHERE dateTime=?", (new_rain,data[0]))
            conexion.commit()
            cursor.execute("UPDATE archive set rainRate=? WHERE dateTime=?", (new_rain_rate,data[0]))
            conexion.commit()

        bar1.finish()

conexion.close()

print("")
if siono == "si" or siono == "Si" or siono == "SI":
    print( Fore.GREEN + "Los valores de " + str(nombre_ddbb) + " han sido modificados satisfactoriamente"  )
    print(  "Pulse intro para salir " + Fore.RESET   )
    msvcrt.getch()
    exit()
else:
    print(  Fore.RED +  "Los valores de " + str(nombre_ddbb) + " no han sufrido cambios"   )
    print(  "Pulse intro para salir " + Fore.RESET   )
    msvcrt.getch()
    exit()