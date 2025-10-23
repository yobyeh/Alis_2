#include <OctoWS2811.h>

// ====== LED configuration ======
static const int TOTAL_PIXELS = 700; // 700 LEDs in a single long strip

// OctoWS2811 requires 6 ints per LED
DMAMEM int displayMemory[TOTAL_PIXELS * 6];
int       drawingMemory[TOTAL_PIXELS * 6];

const int config = WS2811_RGB | WS2811_800kHz;
OctoWS2811 leds(TOTAL_PIXELS, displayMemory, drawingMemory, config);

// ---------- helpers ----------
// No matrix mapping needed; treat as a flat strip
inline int frameIndexToOctoPixel(int i) {
  return i;
}
inline uint32_t packRGB(uint8_t r, uint8_t g, uint8_t b) {
  // Octo's setPixel() expects RGB; wire order handled by 'config'
  return ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}
inline uint8_t scale8(uint8_t v, uint8_t pct) { return (uint16_t)v * pct / 100; }

void solid(uint8_t r, uint8_t g, uint8_t b, uint8_t br = 100) {
  uint32_t c = packRGB(scale8(r, br), scale8(g, br), scale8(b, br));
  for (int i = 0; i < TOTAL_PIXELS; ++i) leds.setPixel(i, c);
  leds.show();
}


// Boot test: RGB cycle, then cumulative color effect
void bootTestSequence() {
  const uint8_t test_brightness = 25; // 25% brightness
  // Send multiple black frames to ensure all LEDs are latched
  for (int i = 0; i < 3; ++i) {
    solid(0, 0, 0, 100);
    leds.show();
    delay(20);
  }

  // 1. All red, green, blue (2s each)
  for (int i = 0; i < 3; ++i) {
    solid(255, 0, 0, test_brightness);
    leds.show();
    delay(20);
  }
  delay(1940); // Subtract the extra delays (3x20ms = 60ms)
  solid(0, 255, 0, test_brightness);
  leds.show();
  delay(10); // Extra latch for first frame
  leds.show();
  delay(1990); // Subtract the extra delay
  solid(0, 0, 255, test_brightness);
  leds.show();
  delay(10); // Extra latch for first frame
  leds.show();
  delay(1990); // Subtract the extra delay
  solid(0, 0, 0, 100); delay(10);

  // 2. Cumulative color effect, 20 LEDs per second (50ms per LED)
  for (int i = 0; i < TOTAL_PIXELS; ++i) {
    // Cycle through a color wheel for each LED
    uint8_t r, g, b;
    float pos = (float)i / TOTAL_PIXELS;
    float angle = pos * 6.2831853f; // 0 to 2pi
    r = (uint8_t)(scale8((sin(angle) * 0.5f + 0.5f) * 255, test_brightness));
    g = (uint8_t)(scale8((sin(angle + 2.0944f) * 0.5f + 0.5f) * 255, test_brightness));
    b = (uint8_t)(scale8((sin(angle + 4.1888f) * 0.5f + 0.5f) * 255, test_brightness));
    leds.setPixel(i, packRGB(r, g, b));
    leds.show();
    delay(50); // 20 per second
  }
  // Leave all on at end
  delay(3000); // Wait 3 seconds
  solid(0, 0, 0, 100); // Clear all LEDs
}

// Read exactly n bytes (single outer timeout, byte-by-byte for tight control)
bool readExact(uint8_t* buf, size_t n, uint32_t timeout_ms = 5000) {
  uint32_t start = millis(); size_t got = 0;
  while (got < n && (millis() - start) < timeout_ms) {
    if (Serial.available()) {
      buf[got++] = (uint8_t)Serial.read();
    } else {
      yield();
    }
  }
  return got == n;
}

// Scan until we see header magic AB CD F1 00
bool waitForHeader(uint32_t timeout_ms = 5000) {
  const uint8_t MAGIC[4] = {0xAB,0xCD,0xF1,0x00};
  uint8_t win[4] = {0,0,0,0};
  uint32_t start = millis();
  while (millis() - start < timeout_ms) {
    if (Serial.available()) {
      win[0] = win[1]; win[1] = win[2]; win[2] = win[3];
      win[3] = (uint8_t)Serial.read();
      if (win[0]==MAGIC[0] && win[1]==MAGIC[1] && win[2]==MAGIC[2] && win[3]==MAGIC[3]) {
        return true;
      }
    } else {
      delay(1);
    }
  }
  return false;
}

void setup() {
  Serial.begin(115200);   // baud ignored on USB, but required by API
  pinMode(LED_BUILTIN, OUTPUT);
  leds.begin(); leds.show();

  // Boot test sequence (RGB cycle, then cumulative green)
  bootTestSequence();

  // small delay so the host can open the port
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 2000) { /* wait up to 2s */ }

  // Announce once (no spam)
  Serial.print("RDY\n");
}

void loop() {
  // Toggle on-board LED slowly while idle
  static uint32_t tHb = 0;
  if (millis() - tHb > 500) { tHb = millis(); digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); }

  // ---- sync to header ----
  if (!waitForHeader()) return;

  // ---- read length + brightness ----
  uint8_t meta[3];
  if (!readExact(meta, 3)) return;
  uint16_t num_pixels = (uint16_t)meta[0] | ((uint16_t)meta[1] << 8);
  uint8_t  br         = meta[2];
  if (br > 100) br = 100;

  if (num_pixels != TOTAL_PIXELS) {
    // Drain the announced payload fully (avoid partial leftovers spoofing header)
    uint32_t toDrain = (uint32_t)num_pixels * 3;
    uint32_t t0 = millis();
    while (toDrain && millis() - t0 < 1000) {
      if (Serial.available()) { Serial.read(); --toDrain; }
      else yield();
    }
    Serial.print("ERR LEN\n");
    return;
  }

  // ---- read payload (GRB) and render ----
  for (uint32_t i = 0; i < num_pixels; ++i) {
    uint8_t g,r,b;
    if (!readExact(&g,1) || !readExact(&r,1) || !readExact(&b,1)) { Serial.print("ERR TO\n"); return; }
    if (br < 100) { g = scale8(g,br); r = scale8(r,br); b = scale8(b,br); }
    // payload is GRB; convert to RGB for setPixel()
    leds.setPixel(frameIndexToOctoPixel(i), packRGB(r,g,b));
  }

  leds.show();
  delay(20); // Ensure hardware is ready
  Serial.print("ACK\n");
}