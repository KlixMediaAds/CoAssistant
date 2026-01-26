import pyaudio
import os
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def main():
    print('\n' + '='*60)
    print(' CO-ASSISTANT CONFIGURATION WIZARD')
    print('='*60)
    
    # --- 1. SET API KEY ---
    print('\n[STEP 1] SETUP API KEY')
    new_key = input('Paste your OpenAI API Key (sk-...) here: ').strip()
    
    if not new_key:
        print('❌ Error: Key cannot be empty.')
        return

    # --- 2. SELECT AUDIO SOURCE ---
    p = pyaudio.PyAudio()
    print('\n[STEP 2] SELECT AUDIO SOURCE')
    print('To hear the CALL (System Audio), look for "Stereo Mix", "Loopback", or "Voicemeeter Output".')
    print('To hear YOURSELF, look for "Microphone".\n')
    
    print(f'{'ID':<4} | {'DEVICE NAME':<40}')
    print('-'*50)
    
    valid_ids = []
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"{i:<4} | {info['name'][:40]}")
                valid_ids.append(str(i))
        except: pass
        
    print('-'*50)
    
    dev_index = input('Enter the ID number to use: ').strip()
    
    if dev_index not in valid_ids:
        print('⚠️ Invalid ID selected. Defaulting to 1.')
        dev_index = "1"

    # --- 3. SAVE CONFIGURATION ---
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(f'OPENAI_API_KEY={new_key}\n')
        f.write(f'DEVICE_INDEX={dev_index}\n')
        
    print('\n✅ CONFIGURATION SAVED!')
    print('You can now run "python app.py"')

if __name__ == '__main__':
    main()
