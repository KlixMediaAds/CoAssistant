import pyaudio
import struct
import math
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Likely candidates for your setup
IDS_TO_TEST = [0, 1, 26, 65, 101]

p = pyaudio.PyAudio()

print('\n' + '='*60)
print('STARTING AUDIO CHECK (PYTHON 3.13 COMPATIBLE)')
print('PLEASE SPEAK CONTINUOUSLY...')
print('='*60)

for device_index in IDS_TO_TEST:
    try:
        info = p.get_device_info_by_index(device_index)
        name = info['name'][:40]
        print(f'\n--- TESTING ID {device_index}: {name} ---')
        
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            input_device_index=device_index,
                            frames_per_buffer=1024)
        except Exception as e:
            print(f'Could not open stream: {e}')
            continue

        max_vol = 0
        # Listen for ~2.5 seconds
        for _ in range(25): 
            try:
                data = stream.read(1024, exception_on_overflow=False)
                # Convert raw bytes to integers (16-bit signed)
                shorts = struct.unpack(f"{len(data)//2}h", data)
                # Calculate volume (RMS)
                sum_squares = sum(s*s for s in shorts)
                rms = math.sqrt(sum_squares / len(shorts))
                
                max_vol = max(max_vol, rms)
                
                # Visual bar
                bars = '█' * int(rms / 200) 
                print(f'\rVol: {bars:<50}', end='')
            except Exception:
                pass
        
        stream.stop_stream()
        stream.close()
        
        if max_vol > 300:
            print(f'\n✅ PASSED! Device {device_index} heard you.')
        else:
            print(f'\n❌ FAILED. Device {device_index} heard silence.')
            
    except Exception as e:
        print(f'\n⚠️ ERROR on ID {device_index}: {e}')

p.terminate()
