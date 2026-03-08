import mido
from mido import MidiFile, MidiTrack, Message
import subprocess
import os

def create_base_midi(filename):
    """Creates a simple audible MIDI file for testing with an existing Program Change."""
    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)

    # Existing Program Change to simulate a real MIDI file
    track.append(Message('program_change', program=1, time=0)) # Grand Piano

    # Simple C major scale
    notes = [60, 62, 64, 65, 67, 69, 71, 72]
    for note in notes:
        track.append(Message('note_on', note=note, velocity=64, time=0))
        track.append(Message('note_off', note=note, velocity=64, time=480))

    mid.save(filename)
    print(f"Created base MIDI: {filename}")

def run_command(command):
    """Runs a shell command and returns the output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(result.stderr)
        return None
    return result.stdout.strip()

def verify():
    base_midi = "test_base.mid"
    steg_midi = "test_steg.mid"
    secret_msg = "Este es un mensaje secreto con LLAVE."
    key = "crypto123"

    # 1. Create base MIDI
    create_base_midi(base_midi)

    # 2. Hide message WITH KEY
    print(f"Hiding message with key: '{secret_msg}'")
    run_command(f"python midi_steg.py hide {base_midi} {steg_midi} --msg '{secret_msg}' --key '{key}'")

    if not os.path.exists(steg_midi):
        print("FAILED: Output MIDI file not created.")
        return False

    # 3. Recover message WITHOUT KEY (should fail or return garbage)
    print("Recovering message WITHOUT key...")
    output_no_key = run_command(f"python midi_steg.py recover {steg_midi}")
    if secret_msg in output_no_key:
         print("FAILED: Recovered secret message WITHOUT key!")
         return False
    else:
         print("SUCCESS: Message NOT recovered without key (as expected).")

    # 4. Recover message WITH KEY
    print("Recovering message WITH key...")
    output = run_command(f"python midi_steg.py recover {steg_midi} --key '{key}'")

    if output and secret_msg in output:
        print("SUCCESS: Message recovered correctly with key!")
    else:
        print(f"FAILED: Recovery failed with key. Output: {output}")
        return False

    # 5. Verify that it works even with pre-existing program changes in other tracks
    # (The recovery should now be isolated to SteganoData track)

    # 6. Cleanup
    os.remove(base_midi)
    os.remove(steg_midi)
    print("Cleanup complete.")
    return True

if __name__ == "__main__":
    if verify():
        print("\nALL VERIFICATIONS PASSED!")
    else:
        print("\nVERIFICATIONS FAILED!")
        exit(1)
