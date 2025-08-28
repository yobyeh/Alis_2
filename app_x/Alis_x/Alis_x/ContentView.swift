import SwiftUI
import CoreBluetooth

/// View model responsible for scanning and connecting to the Pi over Bluetooth.
final class BluetoothViewModel: NSObject, ObservableObject, CBCentralManagerDelegate {
    @Published var status: String = "Searching for Pi..."

    private var central: CBCentralManager!
    private var targetName = "AlisPi" // expected Bluetooth name of the Pi

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            status = "Scanning..."
            central.scanForPeripherals(withServices: nil, options: nil)
        case .unsupported:
            status = "Bluetooth unsupported"
        case .unauthorized:
            status = "Bluetooth unauthorized"
        case .poweredOff:
            status = "Bluetooth off"
        default:
            status = "Bluetooth unavailable"
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String : Any], rssi RSSI: NSNumber) {
        if peripheral.name == targetName {
            status = "Found \(targetName). Connecting..."
            central.stopScan()
            central.connect(peripheral, options: nil)
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        status = "Connected to \(targetName)!"
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        status = "Failed to connect"
    }
}

struct ContentView: View {
    @StateObject private var bluetoothVM = BluetoothViewModel()

    var body: some View {
        VStack(spacing: 20) {
            Text("Bluetooth Test")
                .font(.title)
            Text(bluetoothVM.status)
                .multilineTextAlignment(.center)
                .padding()
        }
    }
}

#Preview {
    ContentView()
}
