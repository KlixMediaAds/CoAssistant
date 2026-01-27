import pyaudio
import time

def test_microphone():
    p = pyaudio.PyAudio()
    print("\n--- SCANNING AUDIO DEVICES ---\n")

    # 1. List all devices
    valid_devices = []
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            # We only care about INPUT devices (Microphones)
            if info['maxInputChannels'] > 0:
                print(f"Index {i}: {info['name']}")
                valid_devices.append(i)
        except:
            pass

    # 2. Ask user to test a specific one
    print("\n--------------------------------")
    target_index = input("Enter the Index Number you want to test (e.g. 5): ")

    try:
        target_index = int(target_index)
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=48000, input=True, input_device_index=target_index, frames_per_buffer=1024)

        print(f"\n[LISTENING on Index {target_index}] - Please speak now...")
        print("Press Ctrl+C to stop.\n")

        while True:
            data = stream.read(1024, exception_on_overflow=False)
            # Convert byte data to integer peak volume
            peak = max(data)

            # Visual Bar
            # The 'peak' value usually ranges from 0 to 255 for 8-bit, or higher for 16-bit.
            # We normalize it for the visual bar.
            bar_length = int(peak / 100)  # Adjust divisor if sensitivity is off
            if bar_length > 50: bar_length = 50

            print(f"\rLevel: {'|' * bar_length}".ljust(60), end="")

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        p.terminate()

if __name__ == "__main__":
    test_microphone()

