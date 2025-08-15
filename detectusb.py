import pywinusb.hid as hid

class GlassesHMI:
    def __init__(self, vendor_id, product_id):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None

        self.id_button = None
        self.previous_id_button = None
        self.button_triggered = False

    def find(self):
        """Find and connect to the USB device"""
        device_filter = hid.HidDeviceFilter(vendor_id=self.vendor_id, product_id=self.product_id)
        devices = device_filter.get_devices()
        print(f"Found {len(devices)} devices matching VID: {self.vendor_id}, PID: {self.product_id}")
        
        if devices:
            for idx, device in enumerate(devices):
                print(f"[{idx}] Device: {device.vendor_name} ({device.product_name})")
            input_idx = int(input("Select device index: "))
            self.device = devices[input_idx]
            print(f"Connected to: {self.device.vendor_name} ({self.device.product_name})")
        else:
            print("No matching USB device found.")

    def open(self):
        """Open the device and set up the data handler"""
        if self.device:
            self.device.set_raw_data_handler(self._data_handler)
            self.device.open()
            print("Device opened and ready.")
        else:
            print("Device not found, cannot open.")

    def _data_handler(self, data):
        """Handle and decode any incoming USB data"""
        print(f"\n[USB DATA] Raw buffer ({len(data)} bytes): {data}")

        # ➤ Extraction ASCII (imprimables)
        ascii_str = self._extract_ascii(data)
        if ascii_str:
            print(f"→ ASCII detected: {ascii_str}")

        # ➤ Analyse brute complète des octets
        self._inspect_raw_bytes(data)

        # ➤ Tu peux garder ton code de bouton si nécessaire
        if len(data) == 3:
            self.previous_id_button = self.id_button
            self.id_button = data[1]
            if self.id_button == 0 and self.previous_id_button:
                match self.previous_id_button:
                    case 140:
                        print("Button center pressed")
                    case 141:
                        print("Button center(sound) pressed")
                    case 143:
                        print("Button + pressed")
                    case 139:
                        print("Button - pressed")
                    case _:
                        print(f"Unknown button ID: {self.previous_id_button}")

    def _extract_ascii(self, data):
        """Extract printable ASCII characters from HID data"""
        ascii_chars = [chr(b) for b in data if 32 <= b <= 126]
        result = ''.join(ascii_chars)
        return result if result else None

    def _inspect_raw_bytes(self, data):
        """Inspect each byte: print as char (if printable), binary, and decimal"""
        print("\n[DECODE]")
        for i, byte in enumerate(data):
            char = chr(byte) if 32 <= byte <= 126 else '.'
            print(f"Byte {i:02d}: dec={byte:<3} hex=0x{byte:02X} bin={format(byte, '08b')} char='{char}'")


    def close(self):
        """Close the device connection"""
        if self.device:
            self.device.close()
            print("Device closed.")


# Example usage
THINKREALITY_VENDOR_ID = 0x17EF
THINKREALITY_PRODUCT_ID = 0xB813

if __name__ == "__main__":
    glasses = GlassesHMI(
        vendor_id=THINKREALITY_VENDOR_ID,
        product_id=THINKREALITY_PRODUCT_ID
    )
    glasses.find()
    glasses.open()

    input("Press Enter to exit...\n")
    glasses.close()
