import Foundation
import CoreBluetooth
import PhotosUI

/// Handles scanning for the Pi and sending files once connected.
final class BluetoothManager: NSObject, ObservableObject {
    @Published var devices: [CBPeripheral] = []
    @Published var connected: CBPeripheral?

    @Published var status: String = "Initializing Bluetooth"


    private var central: CBCentralManager!
    private var transferCharacteristic: CBCharacteristic?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }


    /// Manually trigger a scan if Bluetooth is already powered on.
    func startScan() {
        if central.state == .poweredOn {
            status = "Scanning..."
            central.scanForPeripherals(withServices: nil, options: nil)
        }
    }


    func connect(_ peripheral: CBPeripheral) {
        central.connect(peripheral, options: nil)
    }

    /// Send the file at ``url`` to the connected Pi.
    func sendFile(url: URL) {
        guard let peripheral = connected, let characteristic = transferCharacteristic else { return }
        if let data = try? Data(contentsOf: url) {
            let chunkSize = 512
            var offset = 0
            while offset < data.count {
                let end = min(offset + chunkSize, data.count)
                let chunk = data.subdata(in: offset..<end)
                peripheral.writeValue(chunk, for: characteristic, type: .withResponse)
                offset = end
            }
        }
    }
}

extension BluetoothManager: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:

            startScan()

        case .unauthorized: status = "Bluetooth unauthorized"
        case .poweredOff: status = "Bluetooth off"
        default: status = "Bluetooth unavailable"
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String : Any], rssi RSSI: NSNumber) {
        if !devices.contains(peripheral) {

            DispatchQueue.main.async {
                self.devices.append(peripheral)
            }

        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {

        DispatchQueue.main.async {
            self.status = "Connected to \(peripheral.name ?? "Pi")"
            self.connected = peripheral
        }

        peripheral.delegate = self
        peripheral.discoverServices(nil)
    }
}

extension BluetoothManager: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        for service in peripheral.services ?? [] {
            peripheral.discoverCharacteristics(nil, for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService,
                    error: Error?) {
        for char in service.characteristics ?? [] {
            // assume writable characteristic
            if char.properties.contains(.write) {

                DispatchQueue.main.async {
                    self.transferCharacteristic = char
                    self.status = "Ready to send"
                }

            }
        }
    }
}
