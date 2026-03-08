# criptografia
Learn cryptography in Andes University - COL

# MIDI Steganography - Cryptography Workshop
Este proyecto oculta información dentro de un archivo MIDI mediante Python y la biblioteca Mido.

Los datos ocultos se almacenan en el bit menos significativo (LSB) de los valores de velocidad de las notas MIDI.

## Requirements
Python 3.8+

Install dependencies:

pip install -r requirements.txt

## Ocultar un mensaje secreto
python midi_stegano.py hide midi_samples/VampireKillerCV1.mid output/stego.mid --text "Secret message"

## Extraer el mensaje oculto
python midi_stegano.py extract output/stego.mid --text

## Ocultar un archivo
python midi_stegano.py hide midi_samples/VampireKillerCV1.mid output/stego.mid --payload-file secret.bin

## Para extraer el archivo oculto
python midi_stegano.py extract output/stego.mid --output-file recovered.bin