from RealtimeSTT import AudioToTextRecorder
import os
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def main():
    print('\n' + '='*60)
    print('INITIALIZING AI ENGINE (DEVICE 1)...')
    print('Ignore the float16/float32 warnings below.')
    print('='*60)

    try:
        # Using the exact settings patched into your app.py
        recorder = AudioToTextRecorder(
            model="tiny",
            language="en",
            input_device_index=1,  # Forcing the LOUD microphone
            spinner=True,
            enable_realtime_transcription=True,
            webrtc_sensitivity=1,  # Low aggression
            silero_sensitivity=0.05,
            post_speech_silence_duration=1.2
        )
        
        print('\n' + '='*60)
        print('✅ ENGINE READY! SPEAK NOW.')
        print('Press CTRL+C to stop.')
        print('='*60 + '\n')
        
        while True:
            text = recorder.text()
            if text:
                print(f"TRANSCRIPT: {text}")

    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    main()
