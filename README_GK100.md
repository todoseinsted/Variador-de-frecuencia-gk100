# Control del variador GK100 desde Raspberry PLC 19R por RS-485

## Seguridad y cableado

Antes de cablear, desenergice PLC y variador. El motor puede arrancar al recibir un comando: pruebe primero sin carga mecánica, tenga disponible la parada de emergencia y no la implemente solamente por software.

Conecte el primer RS-485 del PLC al variador:

- `A1+` del PLC a `S+` del GK100.
- `B1-` del PLC a `S-` del GK100.
- Use par trenzado apantallado. Conecte la pantalla a tierra en un solo extremo.
- En una línea larga, coloque 120 ohm entre `S+` y `S-` en ambos extremos del bus. No use topología estrella.

Si no hay respuesta, verifique primero la polaridad: algunos fabricantes nombran A/B de manera inversa. No conecte RS-485 a los bornes de potencia ni a entradas analógicas.

## Parámetros del GK100

Configure desde el panel, con el motor detenido:

- `F0-02 = 2`: mando de marcha por comunicación.
- `F0-03 = 9`: frecuencia principal por Modbus.
- `FC-00 = 5`: 9600 bit/s.
- `FC-01 = 3`: 8 bits, sin paridad, 1 bit de parada (8N1).
- `FC-02 = 1`: dirección Modbus 1.
- `FC-05 = 1`: protocolo Modbus estándar.
- Deje `FC-04 = 0.0 s` durante las primeras pruebas. Luego puede configurar un timeout acorde a la aplicación.

Compruebe también que `F0-10` sea realmente 50.00 Hz. El programa usa ese valor para convertir Hz al porcentaje Modbus.

## Uso del programa

La sintaxis general es:

```bash
python3 controlar_gk100.py [opciones de comunicacion] accion
```

Sin indicar una acción, el programa solamente lee el estado. Las opciones de comunicación deben escribirse **antes** de la acción.

### Primera comprobación

El primer puerto RS-485 del PLC 19R V6 suele ser `/dev/ttySC2`:

```bash
sudo apt install python3-serial
python3 controlar_gk100.py estado
```

Una respuesta normal con el variador detenido es:

```text
Estado: detenido | f=0.00 Hz | U=0.0 V | I=0.00 A | falla=0x0000
```

Esto confirma que existe comunicación Modbus. `U` e `I` son magnitudes de salida hacia el motor, no valores de la alimentación presente en R/S/T.

### Marcha y parada

Para una primera prueba a 5 Hz:

```bash
python3 controlar_gk100.py frecuencia 5
python3 controlar_gk100.py directa
sleep 3
python3 controlar_gk100.py estado
python3 controlar_gk100.py parar
```

`parar` aplica la rampa de desaceleración configurada en el variador. `parada-libre` corta el mando y deja detener el motor por inercia:

```bash
python3 controlar_gk100.py parada-libre
```

Para invertir el sentido, primero detenga el motor, espere a que la lectura indique `detenido` y luego use:

```bash
python3 controlar_gk100.py reversa
```

No use un cambio directo de `directa` a `reversa` durante las primeras pruebas.

### Comandos disponibles

| Comando | Acción |
|---|---|
| `estado` | Lee estado, frecuencia, tensión, corriente y falla |
| `frecuencia HZ` | Fija la referencia de velocidad |
| `directa` | Marcha en sentido directo |
| `reversa` | Marcha en sentido inverso |
| `jog-directa` | JOG en sentido directo |
| `jog-reversa` | JOG en sentido inverso |
| `parar` | Parada con rampa de desaceleración |
| `parada-libre` | Parada por inercia |
| `reset-falla` | Restablece una falla después de corregir su causa |

Para ver la ayuda incorporada:

```bash
python3 controlar_gk100.py --help
python3 controlar_gk100.py frecuencia --help
```

### Frecuencia máxima

El programa presupone que `F0-10` está configurado en 50 Hz. Para un `F0-10` distinto debe informarse el mismo valor mediante `--maxima`. Por ejemplo, una consigna de 30 Hz cuando `F0-10 = 60 Hz`:

```bash
python3 controlar_gk100.py frecuencia 30 --maxima 60
```

No utilice `--maxima` para superar el límite configurado en el variador: ambos valores deben coincidir.

### Otro puerto o configuración serie

Para probar el segundo RS-485:

```bash
python3 controlar_gk100.py --puerto /dev/ttySC3 estado
```

Ejemplo para ID 2 y 19200 bit/s:

```bash
python3 controlar_gk100.py --id 2 --baudios 19200 estado
```

El ID, los baudios, la paridad y los bits de parada deben coincidir con `FC-00`, `FC-01` y `FC-02` del GK100.

## Diagnóstico rápido

- `Sin respuesta completa`: revise alimentación, `A1+`/`S+`, `B1-`/`S-`, puerto, ID, baudios y formato serie.
- El comando responde pero continúa `detenido`: compruebe `F0-02 = 2`.
- Arranca pero no respeta la consigna: compruebe `F0-03 = 9` y que `--maxima` coincida con `F0-10`.
- `falla=0x0000`: no hay una falla activa. Otro número corresponde a la tabla 9-14 del manual.
- Con el variador detenido es normal leer frecuencia, tensión y corriente de salida iguales a cero.
- Sin motor conectado es normal que la corriente permanezca en cero aun cuando la salida esté activa.

## Ejemplos adicionales

```bash
python3 controlar_gk100.py frecuencia 10
python3 controlar_gk100.py directa
python3 controlar_gk100.py parar
```

El manual especifica función Modbus 03 para lectura y 06 para escritura. El programa utiliza `0x1000` para la consigna, `0x2000` para mando, `0x3000` para estado y `0x8000` para la falla. No resta uno a estas direcciones.
