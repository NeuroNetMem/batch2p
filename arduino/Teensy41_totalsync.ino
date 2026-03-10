/*
  /* Event recorder for Virtual Reality behavioral Setups.
  /*Configurable inputs and outputs sampled at 1kFz interval
*/

//Here you can find all the parameters specific to your experiment
//Library if an encoder is use
//#include <Encoder.h>

//Definition pin in use on teensy (example)
#define CAMERA1 14
#define CAMERA2 15

/* If you want a moving average on analog channel
  //Moving average
  const int windowSize = 10;    // size of moving average window
  int lickReadings[windowSize]; // the readings from the lick input
  int windowIndex = 0;          // the index of the current reading
  int totalLickReadings = 0;    // the running total
  int averageLickReadings = 0;  // the average
  int lickThresh = 160;         // Threshold of detection
  bool binaryLick = false;
*/

//Encoder parameters
//Encoder wheelEncoder(WHEEL_ENC_PINA, WHEEL_ENC_PINB);
//long encoderPosition = 0; //Encoder

//if specific values needed
int reward = 0;
int lick = 0;
int lickBaselineCorr;
int lickBaseline;
int frame = 0;
int camera_trigger = 0;
//End of modifiable parameters

//Librairies
#include <FastCRC.h>
#include <PacketSerial.h>
#include <math.h>

//Data packet
FastCRC16 CRC16;
PacketSerial packetSerialA;
PacketSerial packetSerialB;

//Definition Analog and Digital pin and States channel
const int pinsAnalogIn[] = {16, 17, 18, 19, 20, 21, 22, 23};
const int nAnalogIn = sizeof(pinsAnalogIn) / sizeof(pinsAnalogIn[0]);
const int pinsDigitalIn[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
const int nDigitalIn = sizeof(pinsDigitalIn) / sizeof(pinsDigitalIn[0]);
const int pinsDigitalOut[] = {24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39};
const int nDigitalOut = sizeof(pinsDigitalOut) / sizeof(pinsDigitalOut[0]);;
const int nStates = 8;

const int pinsDigital[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39};
const int nDigital = sizeof(pinsDigital) / sizeof(pinsDigital[0]);

//Serial port
#define EXTSERIAL Serial1

//Pin used for communication
#define GATHER_INDICATOR 41
#define LOOP_INDICATOR 40

//LED
const int ledPin = LED_BUILTIN;

//Timing values
IntervalTimer gatherTimer;
elapsedMicros current_micros;
elapsedMillis current_millis;

//Parameters
int last_packet_took = 0;

volatile unsigned char counter = 0;
volatile unsigned long packetCount = 0;
volatile long bufferedStates[nStates];

bool gatherNow = false;
bool packetReady = false;


//

int ipacket = 0;

int ephys = 0;
int rad = 0;
int epacket = 0;
int t = 0;

//Definition packet type
enum packetType : uint8_t {
  ptSTATUS,
  ptINSTR,
  ptERROR,
  ptOK,
  ptACK
};

//Synchronization
const uint16_t syncCounterMax = 0x95FF;
const uint16_t syncCounterMin = 0x9500;
volatile uint16_t syncCounter = syncCounterMax;
volatile uint16_t syncCounterFrameInterval = 100;  // count N frames as 'clock'
volatile byte syncCounterIdx = 0;
volatile byte syncCounterSubIdx = 0;
volatile bool updateSyncCounter = true;

//Structure data packet
struct dataPacket {
  uint8_t type;                   // 1 B, packet type
  uint8_t length;                 // 1 B, packet size
  uint16_t crc16;                 // 2 B, CRC16
  unsigned long packetID;         // 4 B, running packet count

  unsigned long us_start;         // 4 B, gather start timestamp
  unsigned long us_end;           // 4 B, transmit timestamp
  uint16_t analog[nAnalogIn];     // 16 B, ADC values
  long variables[nStates];        // 32 B, variables (encoder, speed, etc)
  uint16_t digitalIn;             // 2 B, digital inputs
  uint16_t digitalOut;             // 1 B, digital outputs
  uint8_t padding[1];             // 1 B, align to 4B

  dataPacket() : type(ptSTATUS),
    length(sizeof(dataPacket)),
    crc16(0),
    packetID(packetCount++),
    digitalIn(0),
    digitalOut(0) {}
};

//Instruction packet
enum instructionType : uint8_t {
  instPIN_LOW     = 0,
  instPIN_HIGH    = 1,
  instPIN_TOGGLE  = 2,
  instSET_STATE   = 4,
  instUNITY       = 5,
  instHANDSHAKE   = 149,
  instRESET       = 6
};

const uint8_t strideInstLOW = 2;
const uint8_t strideInstHIGH = 2;
const uint8_t strideInstTOGGLE = 2;
const uint8_t strideInstUNITY = 2;
const uint8_t strideInstSTATE = 5;

union bytesToLong {
  byte bytes[4];
  unsigned long ulong;
  long slong;
};

//Error packet
struct errorPacket {
  uint8_t type;          // 1 B, packet type
  uint8_t length;        // 1 B, packet size
  uint16_t crc16;        // 2 B, CRC16
  unsigned long packetID;// 4 B, running packet count
  unsigned long us_start;// 4 B, gather start timestamp

  char message[16];      // 16 B, error message

  errorPacket() : type(ptERROR),
    length(sizeof(errorPacket)),
    crc16(0),
    packetID(packetCount++) {}
};

// current state, will be overwritten on gather
dataPacket State;

// Option to reset all the values
void reset() {
  noInterrupts();
  //wheelEncoder.write(0); //Encoder
  current_millis = 0;
  current_micros = 0;

  for (int i = 0; i < nStates; i++) {
    bufferedStates[i] = 0;
  }

  for (int i = 0; i < nDigitalOut; i++) {
    digitalWriteFast(pinsDigitalOut[i], LOW);
  }
  for (int i = 0; i < nDigitalIn; i++) {
    digitalWriteFast(pinsDigitalOut[i], LOW);
  }

  interrupts();
}

//Setting up parameters
void setup() {

  pinMode(ledPin, OUTPUT);

  // analog input channels
  analogReadResolution(16); // change the resolution to 16 bits and read A0

  for (int i = 0; i < nAnalogIn; i++) {
    pinMode(pinsAnalogIn[i], INPUT);
  }

  // digital input channel
  for (int i = 0; i < nDigitalIn - 2; i++) {
    pinMode(pinsDigitalIn[i], INPUT);
  }

  // digital output channels
  for (int i = 0; i < nDigitalOut; i++) {
    pinMode(pinsDigitalOut[i], OUTPUT);
  }

  pinMode(GATHER_INDICATOR, OUTPUT);
  pinMode(LOOP_INDICATOR, OUTPUT);

  reset();

  //Start packet
  packetSerialA.begin(57600);
  packetSerialA.setPacketHandler(&onPacketReceived);
  packetSerialA.setStream(&SerialUSB1);
  packetSerialB.begin(57600);
  packetSerialB.setPacketHandler(&onPacketReceived);
  packetSerialB.setStream(&SerialUSB2);

  // start data acquisition ticks, [us] interval
  // lowering priority is required to give the Encoder priority
  // and seems to massively reduce/prevent missed counts
  gatherTimer.priority(200);
  gatherTimer.begin(gather, 1000);

  //Moving average
  /*for (int thisReading = 0; thisReading < windowSize; thisReading++) {
    lickReadings[thisReading] = 0;
    }*/
}


void loop() {

  digitalWriteFast(LOOP_INDICATOR, HIGH);

  // check serial status for data and buffer health
  packetSerialA.update();
  packetSerialB.update();

  //  if (updateSyncCounter) {
  //    updateSyncCounter = false;
  //    if (++syncCounterSubIdx > syncCounterFrameInterval) {
  //      syncCounterSubIdx = 0;
  //      if (++syncCounterIdx > 15) {
  //        syncCounterIdx = 0;
  //        if (++syncCounter > syncCounterMax) {
  //          syncCounter = syncCounterMin;
  //        }
  //      }
  //    }
  //  }


  if (packetReady) {
    State.crc16 = CRC16.kermit((uint8_t*) &State, sizeof(State));
    packetSerialA.send((byte*) &State, sizeof(State));
    packetSerialB.send((byte*) &State, sizeof(State));

    // apply current state vector
    applyState(&State);


    packetReady = false;
  }
  if (packetSerialA.overflow()) {
    EXTSERIAL.println("S_A overflow!");
  }

  if (packetSerialB.overflow()) {
    EXTSERIAL.println("S_B overflow!");
  }

  digitalWriteFast(LOOP_INDICATOR, LOW);
}

void gather() {
  digitalWriteFast(GATHER_INDICATOR, HIGH); // toggle pin to indicate gather start
  dataPacket packet;

  /*TTL
    if(camera_trigger ==1){
     cameraprocess();
     //digitalWriteFast(32,HIGH);
    }
  */

  /*Codebar TTL
    if(ephys==1){
     ephysrand();
    }
  */

  packet.us_start = current_micros;

  for (int i = 0; i < nAnalogIn; i++) {
    packet.analog[i] = analogRead(pinsAnalogIn[i]);
  }

  for (int i = 0; i < nDigitalOut; i++) {
    packet.digitalOut |= digitalReadFast(pinsDigitalOut[i]) << i;
  }

  for (int i = 0; i < nDigitalIn; i++) {
    packet.digitalIn |= digitalReadFast(pinsDigitalIn[i]) << i;
  }

  //
  //  camera_trigger= digitalReadFast(trigger_c);
  //  reward = digitalReadFast(REWARD);
  //  ephys =digitalReadFast(ephys_trigger);
  //  digitalWriteFast(CAMERA1,HIGH);
  //  digitalWriteFast(CAMERA2,HIGH);

  // moving average
//  totalLickReadings = totalLickReadings - lickReadings[windowIndex];
//  lick = analogRead(LICK);
//  lickReadings[windowIndex] = lick;
//  totalLickReadings = totalLickReadings + lickReadings[windowIndex];
//  averageLickReadings  = totalLickReadings / windowSize;
//  windowIndex = windowIndex + 1;
//  lickBaseline = averageLickReadings;
//  lickBaselineCorr = lick - lickBaseline;

  // just to make sure it loops, we have to wrap it around
//  if (windowIndex >= windowSize) {
//    // ...wrap around to the beginning:
//    windowIndex = 0;
//  }
//  if (lickBaselineCorr <= -lickThresh || lickBaselineCorr >= lickThresh) {
//    digitalWriteFast(BLICK, HIGH); // redundant?
//    binaryLick = true;
//  }
//  else {
//    digitalWriteFast(BLICK, LOW);
//    binaryLick = false;
//  }

  //digitalWriteFast(VALVE, reward);

  noInterrupts();
  //long new_pos = wheelEncoder.read();
  //long position_feel = new_pos * 0.0159;
  interrupts();

  for (int p = 0; p < 8; p++) {
    packet.variables[p] = 0L;
  }

  packet.variables[0] = 0;
  packet.variables[1] = 0;
  packet.variables[2] = 0;
  packet.variables[3] = 0;
  packet.variables[4] = 0;
  packet.variables[5] = 0;
  packet.variables[6] = 0;
  packet.variables[7] = last_packet_took;
  packet.us_end = current_micros;

  last_packet_took = current_micros - packet.us_start;
  State = packet;
  packetReady = true;
  digitalWriteFast(GATHER_INDICATOR, LOW); // toggle pin to indicate gather end
}

void dumpBuffer(const uint8_t* buffer, size_t size) {
  EXTSERIAL.println(size, DEC);
  for (size_t i = 0; i < size; i++) {
    EXTSERIAL.print(buffer[i], HEX);
    EXTSERIAL.print(' ');
  }
  EXTSERIAL.println(' ');
}

// If info received
void onPacketReceived(const uint8_t* buffer, size_t size) {
  // if we receive a command, do what it tells us to do...
  if (buffer[0] == ptINSTR) {
    processInstruction(buffer, size);
  } else {
    dumpBuffer(buffer, size);
  }
}

//State machine
void applyState(dataPacket* packet) {
  // apply finite state machine updates here
  counter++;
}

// synchronization pattern linking the camera to the teensy timing by
// sending a pulsed pattern. The pattern is a counter clocked by FSTROBE
// signal from the camera.
void syncBlink() {
  if (!digitalReadFast(PIN_CAMERA_FSTROBE)) {
    digitalWriteFast(PIN_SYNC_LED, (syncCounter >> syncCounterIdx) & 0x1);
    updateSyncCounter = true;
  } else {
  }
}


void processInstruction (const uint8_t* buf, size_t buf_sz) {
  //  struct instructionPacket* ip = (struct instructionPacket*)buf;
  //  char* data = (char*)ip->data;
  uint8_t instruction = buf[4];

  uint8_t stride;
  uint8_t target;
  uint8_t pin;
  bytesToLong bul;

  switch (instruction) {
    case instPIN_LOW:
      stride = strideInstLOW;
      for (uint8_t pIdx = 5; pIdx + stride <= buf_sz; pIdx += stride) {
        target = buf[pIdx];
        pin = pinsDigitalOut[target];
        digitalWriteFast(pin, LOW);
      }
      break;

    case instPIN_HIGH:
      stride = strideInstHIGH;
      for (uint8_t pIdx = 5; pIdx + stride <= buf_sz; pIdx += stride) {
        target = buf[pIdx];
        pin = pinsDigitalOut[target];
        digitalWriteFast(pin, HIGH);
      }
      break;

    case instPIN_TOGGLE:
      stride = strideInstTOGGLE;
      for (uint8_t pIdx = 5; pIdx + stride <= buf_sz; pIdx += stride) {
        target = buf[pIdx];
        pin = pinsDigitalOut[target];
        digitalWriteFast(pin, !digitalReadFast(pin));
      }
      break;

    case instUNITY:
      stride = strideInstUNITY;
      for (uint8_t pIdx = 5; pIdx + stride <= buf_sz; pIdx += stride) {
        target = buf[pIdx];
        pin = pinsDigital[target];
        digitalWrite(pin, !digitalRead(pin));
      }
      break;


    case instSET_STATE:
      stride = strideInstSTATE;
      EXTSERIAL.println("instSet_State");
      for (uint8_t pIdx = 5; pIdx + stride <= buf_sz; pIdx += stride) {
        target = buf[pIdx];
        for (size_t b = 0; b < sizeof(bul); b++) {
          bul.bytes[b] = buf[pIdx + 1 + b];
        }
        EXTSERIAL.print(target, DEC);
        EXTSERIAL.print(':');
        EXTSERIAL.println(bul.slong);
        bufferedStates[target] = bul.slong;
      }
      break;

    case instRESET:
      EXTSERIAL.println("Resetting everything!");
      reset();
      break;

    default:
      EXTSERIAL.println("Unknown command");
      break;
  }
}

void TTL() {
  // apply finite state machine updates here
  ipacket++;
  if (ipacket == 3) {
    digitalWriteFast(PIN1, HIGH); //change Digital Output pin here
    digitalWriteFast(PIN2, HIGH); //change Digital Output pin here
  }
  else if (ipacket == 8) {
    digitalWriteFast(PIN1, LOW); //change Digital Output pin here
    digitalWriteFast(PIN2, LOW); //change Digital Output pin here
    ipacket = 0;
  }
}

void codebar() {
  if (ephys == 1) {
    digitalWriteFast(ephys_sync, (syncCounter >> syncCounterIdx) & 0x1);
    updateSyncCounter = true;
  } else {
  }


}
