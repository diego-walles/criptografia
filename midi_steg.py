import mido
from mido import MidiFile, MidiTrack, Message
import argparse
import os
import sys

class MidiSteganography:
    """
    Class to hide and recover data within MIDI files using Program Change messages.
    Includes an optional XOR encryption layer for cryptographic context.
    """
    MAGIC = b'STG'
    TRACK_NAME = 'SteganoData'

    @staticmethod
    def xor_data(data, key):
        """Simple XOR encryption/decryption with a key."""
        if not key:
            return data
        key_bytes = key.encode('utf-8')
        return bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data)])

    @staticmethod
    def bytes_to_7bit(data):
        """Encodes bytes into a list of 7-bit integers for MIDI compatibility."""
        bits = ""
        for b in data:
            bits += format(b, '08b')

        # Pad bits to be multiple of 7
        while len(bits) % 7 != 0:
            bits += '0'

        values = []
        for i in range(0, len(bits), 7):
            values.append(int(bits[i:i+7], 2))
        return values

    @staticmethod
    def _7bit_to_bytes(values):
        """Decodes a list of 7-bit integers back into bytes."""
        bits = ""
        for v in values:
            bits += format(v, '07b')

        data = bytearray()
        for i in range(0, (len(bits) // 8) * 8, 8):
            data.append(int(bits[i:i+8], 2))
        return bytes(data)

    def hide(self, input_file, data, output_file, key=None):
        """Hides data in the MIDI file by appending a new silent track with Program Change messages."""
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file {input_file} not found.")

        mid = MidiFile(input_file)

        # Apply XOR encryption if key is provided
        processed_data = self.xor_data(data, key)

        # Prepare payload: MAGIC + length (4 bytes) + data
        payload = self.MAGIC + len(processed_data).to_bytes(4, 'big') + processed_data
        values = self.bytes_to_7bit(payload)

        # Create a new track for hidden data
        hidden_track = MidiTrack()
        mid.tracks.append(hidden_track)

        # Add a name to the track for identification
        hidden_track.append(mido.MetaMessage('track_name', name=self.TRACK_NAME, time=0))

        # Distribute Program Change messages.
        for val in values:
            hidden_track.append(Message('program_change', program=val, time=0))

        mid.save(output_file)

    def recover(self, input_file, key=None):
        """Recovers hidden data from a MIDI file by scanning the specific steganography track."""
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file {input_file} not found.")

        mid = MidiFile(input_file)

        all_values = []
        found_steg_track = False

        for track in mid.tracks:
            # Look for our specific track name
            is_steg_track = False
            for msg in track:
                if msg.is_meta and msg.type == 'track_name' and msg.name == self.TRACK_NAME:
                    is_steg_track = True
                    found_steg_track = True
                    break

            if is_steg_track:
                for msg in track:
                    if msg.type == 'program_change':
                        all_values.append(msg.program)
                break # We only need the first matching track

        if not found_steg_track:
            # Fallback: search all tracks if the named track isn't found (for backwards compatibility)
            all_values = []
            for track in mid.tracks:
                for msg in track:
                    if msg.type == 'program_change':
                        all_values.append(msg.program)

        if not all_values:
            return None

        full_bytes = self._7bit_to_bytes(all_values)

        # Search for MAGIC sequence
        idx = full_bytes.find(self.MAGIC)
        if idx == -1:
            return None

        try:
            # Extract length and then the payload
            length_start = idx + len(self.MAGIC)
            length_bytes = full_bytes[length_start : length_start + 4]
            if len(length_bytes) < 4:
                return None
            length = int.from_bytes(length_bytes, 'big')

            payload_start = length_start + 4
            encrypted_data = full_bytes[payload_start : payload_start + length]

            # Decrypt if key is provided
            return self.xor_data(encrypted_data, key)
        except Exception:
            return None

def main():
    parser = argparse.ArgumentParser(description='MIDI Steganography Tool - Hide and recover data in MIDI files.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Hide command
    hide_parser = subparsers.add_parser('hide', help='Hide data in a MIDI file')
    hide_parser.add_argument('input', help='Input MIDI file path')
    hide_parser.add_argument('output', help='Output MIDI file path')
    hide_parser.add_argument('--key', help='Secret key for encryption')
    group = hide_parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--msg', help='Message string to hide')
    group.add_argument('--file', help='File to hide')

    # Recover command
    recover_parser = subparsers.add_parser('recover', help='Recover data from a MIDI file')
    recover_parser.add_argument('input', help='Input MIDI file path')
    recover_parser.add_argument('--key', help='Secret key for decryption')
    recover_parser.add_argument('--output', help='Output file to save recovered data (optional)')

    args = parser.parse_args()

    steg = MidiSteganography()

    try:
        if args.command == 'hide':
            if args.msg:
                data = args.msg.encode('utf-8')
            else:
                with open(args.file, 'rb') as f:
                    data = f.read()

            steg.hide(args.input, data, args.output, key=args.key)
            print(f"Successfully hid {len(data)} bytes in {args.output}")

        elif args.command == 'recover':
            data = steg.recover(args.input, key=args.key)
            if data:
                if args.output:
                    with open(args.output, 'wb') as f:
                        f.write(data)
                    print(f"Recovered data saved to {args.output}")
                else:
                    try:
                        # Try to print as string
                        print(f"Recovered message: {data.decode('utf-8')}")
                    except UnicodeDecodeError:
                        print("Recovered data is binary or wrong key used. Use --output to save it to a file.")
                        print(f"Hex preview: {data.hex()[:64]}...")
            else:
                print("No hidden data found or incorrect key.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
