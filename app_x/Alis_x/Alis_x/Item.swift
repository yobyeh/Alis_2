//
//  Item.swift
//  Alis_x
//
//  Created by john patrick on 8/27/25.
//

import Foundation
import SwiftData

@Model
final class Item {
    var timestamp: Date
    
    init(timestamp: Date) {
        self.timestamp = timestamp
    }
}
