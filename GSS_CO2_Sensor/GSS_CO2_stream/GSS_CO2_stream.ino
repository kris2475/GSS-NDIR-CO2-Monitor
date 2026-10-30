#include <Arduino.h>

#define RXD2 16
#define TXD2 17

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2);
  delay(1000);

  // Configure sensor output mask to ONLY show Filtered CO2 (Z) and Raw CO2 (z)
  Serial2.print("M 6\r\n"); 
  delay(500);

  Serial.println("ESP32 GSS CO2-Only Bridge Initialised");
}

void loop() {
  if (Serial2.available()) {
    String data = Serial2.readStringUntil('\n');
    data.trim();
    if (data.length() > 0) {
      Serial.println(data); // Forwards clean stream to Python
    }
  }
}


