import serial
import serial.tools.list_ports

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    print("Ports série disponibles :")
    for i, port in enumerate(ports):
        print(f"[{i}] {port.device} — {port.description}")
    return ports

def open_serial_port(port_name, baudrate=4800):
    try:
        ser = serial.Serial(port=port_name, baudrate=baudrate, timeout=1)
        print(f"\n✅ Port ouvert : {port_name} à {baudrate} bauds")
        return ser
    except serial.SerialException as e:
        print(f"❌ Erreur d'ouverture : {e}")
        return None

def read_from_serial(ser):
    print("📡 Lecture du port série (Ctrl+C pour quitter) :\n")
    try:
        while True:
            if ser.in_waiting > 0:
                data = ser.readline().decode(errors='ignore').strip()
                if data:
                    print(f"[REÇU] {data}")
    except KeyboardInterrupt:
        print("\n🛑 Fin de la lecture.")
    finally:
        ser.close()
        print("🔌 Port fermé.")

if __name__ == "__main__":
    ports = list_serial_ports()
    if not ports:
        print("Aucun port série trouvé.")
    else:
        index = int(input("\nChoisissez l'index du port à ouvrir : "))
        selected_port = ports[index].device
        baudrate = int(input("Entrez le baudrate (ex: 9600, 115200) : "))
        ser = open_serial_port(selected_port, baudrate)
        if ser:
            read_from_serial(ser)
