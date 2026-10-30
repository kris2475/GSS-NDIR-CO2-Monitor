#include <Arduino.h>

#define RXD2 16
#define TXD2 17

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2);
  Serial.println("GSS CO2 Sensor Parser Initialized");
}

void loop() {
  if (Serial2.available()) {
    String data = Serial2.readStringUntil('\n');
    data.trim(); // Remove whitespace/newlines

    // Check if the string starts with 'Z'
    int zIndex = data.indexOf('Z');
    if (zIndex != -1) {
      // Find where the 'z' starts (or take the rest of the string if 'z' isn't found)
      int lowerZIndex = data.indexOf('z', zIndex + 1);
      
      String valStr = "";
      if (lowerZIndex != -1) {
        // Extract everything between 'Z' and 'z'
        valStr = data.substring(zIndex + 1, lowerZIndex);
      } else {
        // Fallback if lowercase z is missing on this line
        valStr = data.substring(zIndex + 1);
      }
      
      valStr.trim(); // Clean up extra spaces
      int ppm = valStr.toInt(); // Convert to integer

      Serial.print("Filtered CO2: ");
      Serial.print(ppm);
      Serial.println(" ppm");
      
    } else {
      // Print unparsed lines just in case (helps debugging)
      if (data.length() > 0) {
        Serial.print("Raw Data: ");
        Serial.println(data);
      }
    }
  }
}



