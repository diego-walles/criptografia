#!/usr/bin/env python3
"""Hola, mi nombre es Diego Walles y he trabajado este taller de la Universidad de los Andes usando 
esteganografía con MIDI especifamente los recursos de Mido.

¿Que veremos aquí?, basicamente una herramienta orientada a tareas para ocultar información dentro 
de un archivo MIDI que es lo solicitado por el docente Milton, así como recuperar esa información posteriormente

El método que he usado es el siguiente:
1. Incrustar un bit en el bit menos significativo, es decir en (LSB) de la velocidad de la nota
para cada mensaje de nota note_on / note_off message
2. Almacenar un header + payload length + payload bytes
3. Un XOR key para una protección ligera de la secret-key protection para el payload

Revisando https://www.twilio.com/en-us/blog/working-with-midi-data-in-python-using-mido, he lohrado que la validez
estructural del MIDI si tenga un par de cambios mínimos (maximum +/-1 en la velocidad de la nota para touched events)"""

# Por último cabe resaltar, que este código está diseñado con fines educativos conforme al programa de Ingeniería Criptografica
## que estamos realizando en la Universidad de los Andes con el docente Milton. (Dejaré más en el readme, esta parte es solo intro)

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional

import mido

MAGIC = b"MSTG1"  # MIDI STeG, version 1
LENGTH_SIZE = 4   # uint32 big-endian payload size
HEADER_SIZE = len(MAGIC) + LENGTH_SIZE
BITS_PER_BYTE = 8


class StegoError(Exception):
    """Excepción de base para errores de esteganografía."""


class CapacityError(StegoError):
    """Se genera cuando el archivo MIDI no tiene capacidad suficiente."""


class DecodeError(StegoError):
    """Se genera cuando la carga útil oculta no puede ser decodificada."""


@dataclass
class CapacityReport:
    usable_messages: int
    usable_bits: int
    usable_bytes: int


def xor_with_key(data: bytes, key: Optional[str]) -> bytes:
    """Aplicar un flujo XOR de clave repetida derivado de bloques SHA-256.

    Esta parte la hicé opcional y no es un requisito del profe Milton, pero ví que es útil 
    para una versión de clave secreta además de la esteganografía."""

    if not key:
        return data

    key_bytes = key.encode("utf-8")
    out = bytearray(len(data))
    counter = 0
    offset = 0
    while offset < len(data):
        block = hashlib.sha256(key_bytes + counter.to_bytes(8, "big")).digest()
        take = min(len(block), len(data) - offset)
        for i in range(take):
            out[offset + i] = data[offset + i] ^ block[i]
        offset += take
        counter += 1
    return bytes(out)


def bytes_to_bits(data: bytes) -> List[int]:
    bits: List[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits



def bits_to_bytes(bits: Iterable[int]) -> bytes:
    bit_list = list(bits)
    if len(bit_list) % 8 != 0:
        raise ValueError("La cantidad de bits no es múltiplo de 8.")
    out = bytearray()
    for i in range(0, len(bit_list), 8):
        value = 0
        for bit in bit_list[i:i + 8]:
            value = (value << 1) | (bit & 1)
        out.append(value)
    return bytes(out)



def build_packet(payload: bytes, key: Optional[str]) -> bytes:
    protected = xor_with_key(payload, key)
    return MAGIC + len(protected).to_bytes(LENGTH_SIZE, "big") + protected



def parse_packet(packet: bytes, key: Optional[str]) -> bytes:
    if len(packet) < HEADER_SIZE:
        raise DecodeError("No hay suficientes datos para leer la cabecera.")
    if packet[: len(MAGIC)] != MAGIC:
        raise DecodeError(
            "No se encontró la firma oculta. El archivo no contiene datos embebidos con este programa o la clave es incorrecta."
        )
    length = int.from_bytes(packet[len(MAGIC):HEADER_SIZE], "big")
    if len(packet) != HEADER_SIZE + length:
        raise DecodeError("La longitud recuperada no coincide con el contenido extraído.")
    protected = packet[HEADER_SIZE:]
    return xor_with_key(protected, key)



def is_usable_message(msg: mido.Message) -> bool:
    return not msg.is_meta and msg.type in ("note_on", "note_off") and hasattr(msg, "velocity")



def capacity_report(mid: mido.MidiFile) -> CapacityReport:
    usable_messages = 0
    for track in mid.tracks:
        for msg in track:
            if is_usable_message(msg):
                usable_messages += 1
    usable_bits = usable_messages
    usable_bytes = usable_bits // BITS_PER_BYTE
    return CapacityReport(usable_messages, usable_bits, usable_bytes)



def iter_usable_messages(mid: mido.MidiFile):
    for track in mid.tracks:
        for msg in track:
            if is_usable_message(msg):
                yield msg



def embed_bits_in_midi(mid: mido.MidiFile, bits: List[int]) -> None:
    usable = list(iter_usable_messages(mid))
    if len(bits) > len(usable):
        raise CapacityError(
            f"Capacidad insuficiente: se necesitan {len(bits)} bits y solo hay {len(usable)} disponibles."
        )

    for bit, msg in zip(bits, usable):
        velocity = int(msg.velocity)
        msg.velocity = (velocity & 0b11111110) | bit



def extract_n_bits(mid: mido.MidiFile, count: int) -> List[int]:
    bits: List[int] = []
    for msg in iter_usable_messages(mid):
        bits.append(int(msg.velocity) & 1)
        if len(bits) == count:
            return bits
    raise DecodeError(
        f"No fue posible recuperar {count} bits; el archivo solo contiene {len(bits)} bits utilizables."
    )



def hide_payload(input_midi: str, output_midi: str, payload: bytes, key: Optional[str]) -> CapacityReport:
    mid = mido.MidiFile(input_midi, clip=True)
    report = capacity_report(mid)
    packet = build_packet(payload, key)
    bits = bytes_to_bits(packet)

    if len(bits) > report.usable_bits:
        raise CapacityError(
            "El archivo MIDI no tiene suficiente capacidad. "
            f"Capacidad: {report.usable_bits} bits ({report.usable_bytes} bytes aprox.). "
            f"Necesario: {len(bits)} bits ({(len(bits) + 7) // 8} bytes)."
        )

    embed_bits_in_midi(mid, bits)
    mid.save(output_midi)
    return report



def extract_payload(input_midi: str, key: Optional[str]) -> bytes:
    mid = mido.MidiFile(input_midi, clip=True)

    header_bits = extract_n_bits(mid, HEADER_SIZE * BITS_PER_BYTE)
    header = bits_to_bytes(header_bits)

    if header[: len(MAGIC)] != MAGIC:
        raise DecodeError(
            "No se encontró la firma oculta. El archivo no contiene datos embebidos con este programa o la clave es incorrecta."
        )

    payload_len = int.from_bytes(header[len(MAGIC):HEADER_SIZE], "big")
    total_bits = (HEADER_SIZE + payload_len) * BITS_PER_BYTE
    packet_bits = extract_n_bits(mid, total_bits)
    packet = bits_to_bytes(packet_bits)
    return parse_packet(packet, key)



def read_payload_from_args(args: argparse.Namespace) -> bytes:
    if args.text is not None and args.payload_file is not None:
        raise StegoError("Use solo una fuente de datos: --text o --payload-file.")
    if args.text is None and args.payload_file is None:
        raise StegoError("Debe indicar qué ocultar con --text o --payload-file.")
    if args.text is not None:
        return args.text.encode("utf-8")
    with open(args.payload_file, "rb") as fh:
        return fh.read()



def save_or_print_extracted(data: bytes, output_file: Optional[str], as_text: bool) -> None:
    if output_file:
        with open(output_file, "wb") as fh:
            fh.write(data)
        print(f"Datos recuperados y guardados en: {output_file}")
        return

    if as_text:
        try:
            print(data.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise DecodeError(
                "Los datos recuperados no son texto UTF-8. Use --output-file para guardarlos como binario."
            ) from exc
    else:
        sys.stdout.buffer.write(data)



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Oculta y recupera información dentro de archivos MIDI usando Mido."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_capacity = subparsers.add_parser("capacity", help="Muestra la capacidad del archivo MIDI.")
    p_capacity.add_argument("input_midi", help="Archivo MIDI de entrada.")

    p_hide = subparsers.add_parser("hide", help="Oculta datos en un archivo MIDI.")
    p_hide.add_argument("input_midi", help="Archivo MIDI original.")
    p_hide.add_argument("output_midi", help="Archivo MIDI de salida con datos ocultos.")
    p_hide.add_argument("--text", help="Texto UTF-8 a ocultar.")
    p_hide.add_argument("--payload-file", help="Archivo binario a ocultar.")
    p_hide.add_argument("--key", help="Clave opcional para proteger el payload con XOR.")

    p_extract = subparsers.add_parser("extract", help="Recupera datos ocultos desde un archivo MIDI.")
    p_extract.add_argument("input_midi", help="Archivo MIDI con datos ocultos.")
    p_extract.add_argument("--output-file", help="Ruta para guardar los datos recuperados.")
    p_extract.add_argument("--text", action="store_true", help="Interpretar la salida como texto UTF-8 e imprimirla.")
    p_extract.add_argument("--key", help="Clave opcional usada al ocultar.")

    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "capacity":
            mid = mido.MidiFile(args.input_midi, clip=True)
            report = capacity_report(mid)
            print(f"Mensajes utilizables: {report.usable_messages}")
            print(f"Capacidad: {report.usable_bits} bits")
            print(f"Capacidad aproximada: {report.usable_bytes} bytes")
            print("Método: 1 bit por mensaje note_on/note_off usando el LSB de velocity")
            return 0

        if args.command == "hide":
            payload = read_payload_from_args(args)
            report = hide_payload(args.input_midi, args.output_midi, payload, args.key)
            packet_size = HEADER_SIZE + len(payload)
            print(f"Archivo generado: {args.output_midi}")
            print(f"Datos ocultos: {len(payload)} bytes")
            print(f"Tamaño total embebido (cabecera + datos): {packet_size} bytes")
            print(f"Capacidad del MIDI: {report.usable_bytes} bytes aprox.")
            if args.key:
                print("Protección adicional: XOR con clave activada")
            else:
                print("Protección adicional: no activada")
            return 0

        if args.command == "extract":
            data = extract_payload(args.input_midi, args.key)
            save_or_print_extracted(data, args.output_file, args.text)
            return 0

        parser.error("Comando no reconocido.")
        return 2

    except (StegoError, OSError, IOError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())