#include <TinyGPS++.h>
#include <WiFi.h>
#include <HTTPClient.h>

#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

TinyGPSPlus gps;
HardwareSerial neo6m(2);

const char *ssid = "PaviconKE";  
const char *password = "P@vic0N@20$0";

// const char *ssid = "Domi";  
// const char *password = "#Dominic1218"; 

const char* serverName = "https://zebra-advanced-manually.ngrok-free.app/gps";
// const char* serverName = "http://192.168.100.8:8000/gps";

// Simulated GPS data
double simLatitude = 1.2921;    // Example latitude (Nairobi, Kenya)
double simLongitude = 36.8219;  // Example longitude (Nairobi, Kenya)
double simAltitude = 1661.0;    // Example altitude in meters
unsigned long simDate = 20240815;  // Simulated date (YYYYMMDD)
unsigned long simTime = 133000;    // Simulated time (HHMMSS)

void setup() {
  Serial.begin(115200);
  neo6m.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  smartdelay_gps(1000);

  double latitude, longitude, altitude;
  String formattedDate, formattedTime;

  if (gps.location.isValid() && gps.altitude.isValid()) {
    // Use real GPS data
    latitude = gps.location.lat();
    longitude = gps.location.lng();
    altitude = gps.altitude.meters();
    formattedDate = formatDate(gps.date);
    formattedTime = formatTime(gps.time);
  } else {
    // Use simulated GPS data
    Serial.println("Using simulated GPS data...");
    latitude = simLatitude;
    longitude = simLongitude;
    altitude = simAltitude;
    formattedDate = formatSimDate(simDate);
    formattedTime = formatSimTime(simTime);
  }

  Serial.print("Latitude: ");
  Serial.println(latitude, 6);  
  Serial.print("Longitude: ");
  Serial.println(longitude, 6); 
  Serial.print("Altitude: ");
  Serial.print(altitude, 2);  // Limit to 2 decimal places
  Serial.println(" meters");
  Serial.print("Date: ");
  Serial.println(formattedDate);
  Serial.print("Time: ");
  Serial.println(formattedTime);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverName);  // Initialize the HTTP client with the server URL
    http.addHeader("Content-Type", "application/json");

    String jsonPayload = "{\"latitude\": " + String(latitude, 6) +
                         ", \"longitude\": " + String(longitude, 6) +
                         ", \"altitude\": " + String(altitude, 2) +
                         ", \"date\": \"" + formattedDate + "\"" +
                         ", \"time\": \"" + formattedTime + "\"}";

    int httpResponseCode = http.POST(jsonPayload);  // Send the POST request

    if (httpResponseCode > 0) {
      Serial.print("HTTP Response code: ");
      Serial.println(httpResponseCode);
    } else {
      Serial.print("Error code: ");
      Serial.println(httpResponseCode);
    }
    http.end();
  }

  delay(1000);  // Delay for Time
}

static void smartdelay_gps(unsigned long ms) {
  unsigned long start = millis();
  do {
    while (neo6m.available())
      gps.encode(neo6m.read());
  } while (millis() - start < ms);
}

// Function to format GPS date as a string
String formatDate(TinyGPSDate date) {
  char buffer[11];
  snprintf(buffer, sizeof(buffer), "%04d-%02d-%02d", date.year(), date.month(), date.day());
  return String(buffer);
}

// Function to format GPS time as a string
String formatTime(TinyGPSTime time) {
  char buffer[9];
  snprintf(buffer, sizeof(buffer), "%02d:%02d:%02d", time.hour(), time.minute(), time.second());
  return String(buffer);
}

// Function to format simulated date as a string
String formatSimDate(unsigned long simDate) {
  int year = simDate / 10000;
  int month = (simDate % 10000) / 100;
  int day = simDate % 100;

  char buffer[11];
  snprintf(buffer, sizeof(buffer), "%04d-%02d-%02d", year, month, day);
  return String(buffer);
}

// Function to format simulated time as a string
String formatSimTime(unsigned long simTime) {
  int hour = simTime / 10000;
  int minute = (simTime % 10000) / 100;
  int second = simTime % 100;

  char buffer[9];
  snprintf(buffer, sizeof(buffer), "%02d:%02d:%02d", hour, minute, second);
  return String(buffer);
}
