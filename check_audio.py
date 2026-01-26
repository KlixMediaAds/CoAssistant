import pyaudio
import sys

# Force UTF-8 for console output
sys.stdout.reconfigure(encoding='utf-8')

p = pyaudio.PyAudio()

print('\n' + '='*60)
print(f'{'ID':<5} | {'DEVICE NAME':<40} | {"CHANNELS"}')
print('='*60)

count = p.get_device_count()
found = False

for i in range(count):
    try:
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f'{i:<5} | {info["name"][:38]:<40} | {info["maxInputChannels"]}')
            found = True
    except Exception as e:
        pass

print('='*60 + '\n')
p.terminate()
