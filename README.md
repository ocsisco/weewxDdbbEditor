# weewxDdbbEditor
Pequeño script para modificar el acumulado de precipitación en un rango temporal (corrección de falsos valores por mantenimiento, corrección y ajuste de desviaciones de pluviómetros automáticos)

IMPORTANTE

El creador de esta aplicación no se hace responsable de los daños causados sobre las bases de datos a modificar
así como del mal funcionamiento de esta por lo que:
SIEMPRE HAGA UNA COPIA DE SEGURIDAD DE LA BASE DE DATOS ANTES DE SER OPERADA POR LA APLICACIÓN
a continuacion pruebe la base de datos modificada y verifique que todo se muestra correctamente antes de realizar
cambios definitivos.



INSTRUCCIONES

Al inicio del programa este te pedirá que insertes una fecha de inicio y una de fin, el formato de la fecha es: 
YYYY/MM/DD-HH/MM/SS, es irrelevante que la separación sean barras guiones o espacios... 
por ejemplo: "2021-01-01 12:00:20" sería una fecha válida, así como "2021 01 01 12 00 20" o "2021-01-01-12-00-20", 
pero si es importante que el dato sea un conjunto de agrupaciones de dos cifras excepto el año que será de cuatro 
cifras.

Una vez indicadas las fechas de inicio y de fin de un periodo que se desea modificar el programa pedira que
insertes la ubicación relativa de el archivo que se desea modificar, si no se tiene claro como abarcar este punto
el modo mas sencillo sería simplemente colocar el archivo de la base de datos en la misma carpeta donde se ubica 
el .exe e intrducir simplemente el nombre del archivo en la consola.

A continuación el programa mostrará en consola el acumulado de precipitación en ese periodo de tiempo, si desea
modificarlo simplemente escriba "si" y pulse intro, de lo contrario escriba "no" y pulse intro.

Introduzca el acumulado en milímetros para ese periodo y pulse intro.

La consola msotrará el porcentaje del valor introducido respecto al valor de la base de datos, este dato puede ser
de utilidad para realizar las correcciones del pluviómetro automático, a continuación se muestran los datos antes
de ser modificados para una última comprobación, escriba "si" y pulse intro para efectuar el cambio.

Cuando el programa termine, podría tardar algunos minutos si el periodo a modificar abarcara años, pero por lo
general serán unos pocos segundos.



DETALLES A TENER EN CUENTA

El programa respeta los valores de forma proporcional, eso conlleva la gran ventaja de respetar los rainrates y los
registros originales, pero tiene algunas limitaciones a tener en cuenta:

No se puede añadir precipitación en un rango temporal donde no la haya porque el programa tendría que inventarse el 
reparto horario de precipitación y el rainrate.

Para eliminar un registro, por ejemplo, un falso registro que deseamos eliminar debido a movimientos del pluviometro 
durante el mantenimiento, no es posible cambiar el acumulado en ese intervalo de tiempo por 0, porque de nuevo, el 
algoritmo no podría respetar la proporcionalidad de los datos, en estos casos la solución es simplemente cambiar el 
acumulado por una cifra muy pequeña como por ejemplo 0.0001, que no influirá en los acumulados, pero que, aporta 
varias ventajas como por ejemplo, dejar constancia en la bbdd de la alteración o incluso recuperar el dato si se 
hubiese borrado por error simplemente volviendo a cambiar el dato del periodo temporal por el dato correcto.

