#!/usr/bin/env python3
"""Control Modbus RTU del variador GTAKE/Transpower GK100 desde un PLC 19R."""

from __future__ import annotations

import argparse
import struct
import sys
import time

try:
    import serial
except ImportError:
    print("Falta pyserial. Instale: sudo apt install python3-serial", file=sys.stderr)
    raise SystemExit(2)


REG_SETPOINT = 0x1000
REG_FREQUENCY = 0x1001
REG_OUTPUT_VOLTAGE = 0x1003
REG_OUTPUT_CURRENT = 0x1004
REG_COMMAND = 0x2000
REG_STATUS = 0x3000
REG_FAULT = 0x8000

COMMANDS = {
    "directa": 0x0001,
    "reversa": 0x0002,
    "jog-directa": 0x0003,
    "jog-reversa": 0x0004,
    "parada-libre": 0x0005,
    "parar": 0x0006,
    "reset-falla": 0x0007,
}
STATUS = {1: "operando en directa", 2: "operando en reversa", 3: "detenido"}


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def exchange(port: serial.Serial, body: bytes, expected_length: int) -> bytes:
    request = body + struct.pack("<H", crc16(body))
    port.reset_input_buffer()
    port.write(request)
    port.flush()
    response = port.read(expected_length)
    time.sleep(max(0.020, 4 * 11 / port.baudrate))
    if len(response) != expected_length:
        raise TimeoutError(f"respuesta incompleta: {len(response)}/{expected_length} bytes")
    if crc16(response[:-2]) != struct.unpack("<H", response[-2:])[0]:
        raise ValueError("CRC incorrecto")
    if response[0] != body[0]:
        raise ValueError(f"respondio ID {response[0]}, se esperaba {body[0]}")
    if response[1] & 0x80:
        raise ValueError(f"excepcion Modbus {response[2]}")
    return response


def read_words(port: serial.Serial, slave: int, address: int, count: int = 1) -> list[int]:
    body = struct.pack(">BBHH", slave, 3, address, count)
    response = exchange(port, body, 5 + 2 * count)
    if response[1] != 3 or response[2] != 2 * count:
        raise ValueError(f"respuesta de lectura inesperada: {response.hex(' ')}")
    return list(struct.unpack(f">{count}H", response[3:-2]))


def write_word(port: serial.Serial, slave: int, address: int, value: int) -> None:
    body = struct.pack(">BBHH", slave, 6, address, value & 0xFFFF)
    response = exchange(port, body, 8)
    if response[:-2] != body:
        raise ValueError(f"eco de escritura inesperado: {response.hex(' ')}")


def show_status(port: serial.Serial, slave: int) -> None:
    frequency = read_words(port, slave, REG_FREQUENCY)[0] / 100
    # El manual (grupo U0, U0-03) especifica una unidad minima de 1 V.
    voltage = float(read_words(port, slave, REG_OUTPUT_VOLTAGE)[0])
    current = read_words(port, slave, REG_OUTPUT_CURRENT)[0] / 100
    state = read_words(port, slave, REG_STATUS)[0]
    fault = read_words(port, slave, REG_FAULT)[0]
    print(
        f"Estado: {STATUS.get(state, f'codigo 0x{state:04X}')} | "
        f"f={frequency:.2f} Hz | U={voltage:.1f} V | I={current:.2f} A | "
        f"falla=0x{fault:04X}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto", default="/dev/ttySC2")
    parser.add_argument("--id", type=int, default=1)
    parser.add_argument("--baudios", type=int, default=9600)
    parser.add_argument("--paridad", choices=("N", "E", "O"), default="N")
    parser.add_argument("--bits-parada", type=int, choices=(1, 2), default=1)
    sub = parser.add_subparsers(dest="accion")
    sub.add_parser("estado", help="leer estado y mediciones (accion predeterminada)")
    frequency = sub.add_parser("frecuencia", help="fijar consigna en Hz")
    frequency.add_argument("hz", type=float)
    frequency.add_argument("--maxima", type=float, default=50.0, help="F0-10 del variador")
    for command in COMMANDS:
        sub.add_parser(command)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.id <= 247:
        print("El ID debe estar entre 1 y 247.", file=sys.stderr)
        return 2
    parity = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}[args.paridad]
    try:
        with serial.Serial(
            args.puerto, args.baudios, bytesize=serial.EIGHTBITS,
            parity=parity, stopbits=args.bits_parada, timeout=1,
        ) as port:
            if args.accion in (None, "estado"):
                show_status(port, args.id)
            elif args.accion == "frecuencia":
                if args.maxima <= 0 or not 0 <= args.hz <= args.maxima:
                    raise ValueError(f"frecuencia fuera de 0..{args.maxima:g} Hz")
                # 10000 equivale al 100 % de F0-10, segun tabla 9-6.
                setpoint = round(args.hz / args.maxima * 10000)
                write_word(port, args.id, REG_SETPOINT, setpoint)
                print(f"Consigna: {args.hz:.2f} Hz ({setpoint}/10000 de F0-10).")
            else:
                write_word(port, args.id, REG_COMMAND, COMMANDS[args.accion])
                print(f"Comando enviado: {args.accion}.")
        return 0
    except PermissionError:
        print(f"Sin permiso para {args.puerto}; agregue el usuario al grupo dialout.", file=sys.stderr)
    except (OSError, TimeoutError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
