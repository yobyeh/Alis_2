import SwiftUI
import PhotosUI
import CoreBluetooth

struct ContentView: View {
    @StateObject private var bluetooth = BluetoothManager()
    @State private var selectedItem: PhotosPickerItem?

    var body: some View {
        NavigationView {
            VStack {
                Text(bluetooth.status)
                    .padding()
                if bluetooth.devices.isEmpty {
                    Text("No devices found")
                        .foregroundColor(.secondary)
                } else {
                    List(bluetooth.devices, id: \.identifier) { peripheral in
                        Button(peripheral.name ?? "Unknown") {
                            bluetooth.connect(peripheral)
                        }
                    }
                }
                if bluetooth.connected != nil {
                    PhotosPicker("Upload Photo", selection: $selectedItem, matching: .images)
                        .onChange(of: selectedItem) { newItem in
                            Task {
                                if let data = try? await newItem?.loadTransferable(type: Data.self) {
                                    let url = FileManager.default.temporaryDirectory.appendingPathComponent("upload.jpg")
                                    try? data.write(to: url)
                                    bluetooth.sendFile(url: url)
                                }
                            }
                        }
                }
            }
            .navigationTitle("Bluetooth")
            .onAppear {
                bluetooth.startScan()
            }
        }
    }
}

#Preview {
    ContentView()
}
