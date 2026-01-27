import pyaudio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
DEVICE_INDEX = int(os.getenv("DEVICE_INDEX", 11))

def main():
    p = pyaudio.PyAudio()
    
    try:
        info = p.get_device_info_by_index(DEVICE_INDEX)
        print(f"TESTING DEVICE [{DEVICE_INDEX}]: {info['name']}")
        print("Play some loud audio (YouTube/Music)...")
        print("Press Ctrl+C to stop.")
        
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=48000,
                        input=True,
                        input_device_index=DEVICE_INDEX,
                        frames_per_buffer=1024)

        while True:
            data = stream.read(1024, exception_on_overflow=False)
            # Calculate simple volume peak
            peak = max(data) 
            
            # visual bar
            bars = "|" * int(peak / 250)
            if len(bars) > 0:
                print(f"\rVOLUME: {bars[:50]}", end="")
            else:
                print(f"\rVOLUME: (Silence)", end="")
                
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        p.terminate()

if __name__ == "__main__":
    main()

