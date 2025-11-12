# SerDes Architecture Specification

**Document Version**: 1.0
**Last Updated**: 2025-01-11
**Target**: High-Speed SerDes (10-25 Gbps) for PCIe Gen3/4/5
**Modulation**: NRZ, PAM4

---

## 1. System Overview

### 1.1 Purpose

This document defines the **complete SerDes (Serializer/Deserializer) system architecture** for high-speed serial data transmission and reception. It integrates transmitter (Tx), receiver (Rx), equalization blocks (FFE, DFE, CTLE), and analog interfaces (DAC, ADC) into a cohesive system.

### 1.2 Key System Features

- **Data Rates**: 10-25 Gbps per lane
- **Modulation Schemes**: NRZ (2-level), PAM4 (4-level)
- **Transmitter**: DAC-based analog output with FFE pre-emphasis
- **Receiver**: ADC-based sampling with CTLE + FFE + DFE equalization cascade
- **Standard Compliance**: PCIe Gen3/4/5
- **Equalization**: Adaptive transmit and receive equalization
- **Clock Architecture**: Tx PLL + Rx CDR (Clock Data Recovery)

### 1.3 Top-Level Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SERDES SYSTEM                                      │
│                                                                             │
│  ┌──────────────────────────────┐          ┌──────────────────────────────┐│
│  │         TRANSMITTER          │          │          RECEIVER            ││
│  │                              │          │                              ││
│  │  Parallel   ┌──────────┐    │          │    ┌──────────┐  Parallel   ││
│  │  Data In    │          │    │          │    │          │  Data Out    ││
│  │  [31:0] ───►│ TX FFE   ├───►│          │───►│ ADC      ├────┐         ││
│  │  (NRZ/PAM4) │(Pre-     │    │          │    │(8-bit)   │    │         ││
│  │             │emphasis) │    │ Channel  │    └──────────┘    │         ││
│  │             └──────────┘    │          │                    ▼         ││
│  │                  │          │   (PCB   │    ┌──────────────────┐      ││
│  │             ┌────▼───────┐  │   trace, │    │ CTLE (Analog RNM)│      ││
│  │             │ Serializer │  │   cable, │    │ (High-Pass EQ)   │      ││
│  │             │ (P2S)      │  │   conn.) │    └────────┬─────────┘      ││
│  │             └────┬───────┘  │          │             │                ││
│  │                  │          │          │    ┌────────▼─────────┐      ││
│  │             ┌────▼───────┐  │          │    │ RX FFE (7-tap)   │      ││
│  │             │ DAC (Analog│ ─┼──────────┼───►│ (Linear FIR)     │      ││
│  │             │  Driver)   │  │          │    └────────┬─────────┘      ││
│  │             └────────────┘  │          │             │                ││
│  │                              │          │    ┌────────▼─────────┐      ││
│  │  TX_CLK (from PLL)           │          │    │ DFE (5-tap)      │      ││
│  │  ───────────────────────────►│          │    │ (Nonlinear FB)   │      ││
│  │                              │          │    └────────┬─────────┘      ││
│  └──────────────────────────────┘          │             │                ││
│                                            │    ┌────────▼─────────┐      ││
│                                            │    │ Deserializer     │      ││
│                                            │    │ (S2P)            │      ││
│                                            │    └────────┬─────────┘      ││
│                                            │             │                ││
│                                            │    ┌────────▼─────────┐      ││
│                                            │    │ CDR (Clock       │      ││
│                                            │    │ Data Recovery)   │      ││
│                                            │    └──────────────────┘      ││
│                                            │             │ RX_CLK         ││
│                                            └─────────────┴────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Transmitter (Tx) Architecture

### 2.1 Tx Data Path

**Flow**: `Parallel Data → TX FFE → Serializer → DAC → Analog Signal → Channel`

#### 2.1.1 Parallel Data Input

- **Width**: 32-bit parallel (for 10 Gbps: 32 bits @ 312.5 MHz = 10 Gbps serial)
- **Format**:
  - **NRZ**: 1 bit per symbol → 32 symbols per clock
  - **PAM4**: 2 bits per symbol → 16 symbols per clock (32 bits / 2)
- **Encoding**: Pre-encoded (8b/10b or 128b/130b) upstream (not in SerDes scope)

#### 2.1.2 TX FFE (Pre-Emphasis)

**Module**: `tx_ffe.sv` (see `spec/ffe_specification.md`)

- **Purpose**: Pre-distorts Tx signal to pre-compensate for known channel loss
- **Configuration**: Typically 3-7 taps (fewer than Rx FFE)
- **Coefficients**: Programmed based on channel characterization
- **Output**: Pre-emphasized parallel data (still digital)

#### 2.1.3 Serializer (Parallel-to-Serial)

**Module**: `serializer.sv`

- **Function**: Converts 32-bit parallel to 1-bit serial at high speed
- **Clock Domains**:
  - Input: Parallel clock (e.g., 312.5 MHz for 10 Gbps)
  - Output: Serial clock (e.g., 10 GHz for 10 Gbps)
- **Implementation**: Shift register with clock multiplication

#### 2.1.4 DAC (Digital-to-Analog Converter)

**Module**: `dac_model.sv` (behavioral model for simulation)

- **Function**: Converts serial digital bits → analog voltage levels
- **Modulation Mapping**:
  - **NRZ**:
    - `0` → -1.0 V (logic 0)
    - `1` → +1.0 V (logic 1)
  - **PAM4**:
    - `00` → -0.75 V (symbol 0)
    - `01` → -0.25 V (symbol 1)
    - `10` → +0.25 V (symbol 2)
    - `11` → +0.75 V (symbol 3)
- **Output Type**: `real` (analog voltage for RNM simulation)

### 2.2 Tx Clock Architecture

#### 2.2.1 PLL (Phase-Locked Loop)

**Module**: `pll_model.sv` (behavioral model)

- **Input**: Reference clock (e.g., 100 MHz crystal)
- **Output**: High-speed serial clock (e.g., 10 GHz for 10 Gbps NRZ)
- **Multiplication Factor**: 100× for 10 Gbps, 250× for 25 Gbps
- **Jitter**: < 1 ps RMS (for PCIe compliance)

#### 2.2.2 Clock Distribution

```
REF_CLK (100 MHz) ──► PLL ──► Serial CLK (10 GHz) ──► Serializer
                           └──► Parallel CLK (312.5 MHz) ──► TX FFE (÷32)
```

### 2.3 Tx Interface Specification

**Module**: `serdes_tx.sv`

| Port Name          | Direction | Width    | Type           | Description                     |
|--------------------|-----------|----------|----------------|---------------------------------|
| `ref_clk`          | Input     | 1        | `logic`        | Reference clock (e.g., 100 MHz) |
| `rst_n`            | Input     | 1        | `logic`        | Active-low reset                |
| `tx_data_in`       | Input     | 32       | `logic`        | Parallel Tx data (NRZ or PAM4)  |
| `tx_data_valid`    | Input     | 1        | `logic`        | Data valid strobe               |
| `modulation`       | Input     | 1        | `logic`        | 0 = NRZ, 1 = PAM4               |
| `ffe_coeff_wr_en`  | Input     | 1        | `logic`        | FFE coefficient write enable    |
| `ffe_coeff_addr`   | Input     | 3        | `logic`        | FFE tap address                 |
| `ffe_coeff_data`   | Input     | 10       | `logic signed` | FFE coefficient value           |
| `tx_analog_out`    | Output    | N/A      | `real`         | Analog Tx signal (to channel)   |
| `tx_clk_out`       | Output    | 1        | `logic`        | Parallel clock output (for sync)|

---

## 3. Receiver (Rx) Architecture

### 3.1 Rx Data Path

**Flow**: `Analog Signal → ADC → CTLE → RX FFE → DFE → Deserializer → Parallel Data`

#### 3.1.1 ADC (Analog-to-Digital Converter)

**Module**: `adc_model.sv` (behavioral model)

- **Function**: Samples analog Rx signal at serial rate, converts to 8-bit digital
- **Resolution**: 8 bits (256 levels, sufficient for PAM4 + noise margin)
- **Sampling Rate**: Serial rate (e.g., 10 GS/s for 10 Gbps)
- **Input Type**: `real` (analog voltage from channel)
- **Output Type**: `logic [7:0]` (signed, -128 to +127)
- **Quantization**:
  - Map analog range [-1.0 V, +1.0 V] → digital [-128, +127]
  - ADC_out = clamp(round(analog_in × 128), -128, 127)

#### 3.1.2 CTLE (Continuous-Time Linear Equalizer)

**Module**: `ctle_rnm.sv` (see `spec/ctle_specification.md`)

- **Purpose**: Analog high-pass equalization before ADC (boosts high frequencies)
- **Implementation**: Real Number Modeling (RNM) with `real` type
- **Placement**: Typically **before ADC** in real hardware, but in simulation can be after ADC for simplicity
- **Configuration**: Programmable zero/pole frequencies for channel adaptation

**Simulation Note**: For ease of implementation, CTLE can be modeled after ADC operating on 8-bit samples converted to `real` for filtering, then back to `logic [7:0]`.

#### 3.1.3 RX FFE (7-tap Feed-Forward Equalizer)

**Module**: `rx_ffe.sv` (see `spec/ffe_specification.md`)

- **Purpose**: Linear equalization of digitized signal (removes residual ISI)
- **Configuration**: 7 taps (more than Tx FFE for finer control)
- **Input**: 8-bit ADC samples (or CTLE output)
- **Output**: 8-bit equalized samples

#### 3.1.4 DFE (5-tap Decision Feedback Equalizer)

**Module**: `dfe.sv` (see `spec/dfe_specification.md`)

- **Purpose**: Nonlinear equalization using past decisions (cancels post-cursor ISI)
- **Configuration**: 5 feedback taps
- **Input**: Equalized samples from RX FFE
- **Output**: Detected symbols (hard decisions: NRZ levels or PAM4 levels)

#### 3.1.5 Deserializer (Serial-to-Parallel)

**Module**: `deserializer.sv`

- **Function**: Converts serial bit stream → 32-bit parallel words
- **Clock Domains**:
  - Input: Recovered serial clock (from CDR)
  - Output: Parallel clock (serial clock ÷ 32)
- **Implementation**: Shift register with demultiplexing

### 3.2 Rx Clock Architecture

#### 3.2.1 CDR (Clock Data Recovery)

**Module**: `cdr.sv` (behavioral model)

- **Function**: Extracts clock from incoming data stream (no separate clock line)
- **Algorithm**: Phase-locked loop (PLL) + phase detector
- **Input**: Equalized data stream (from DFE or FFE)
- **Outputs**:
  - `recovered_clk`: Serial rate clock (e.g., 10 GHz)
  - `clk_locked`: Lock indicator (CDR has acquired data clock)
- **Lock Time**: ~1000 UI (unit intervals) typical

#### 3.2.2 Clock Distribution

```
Incoming Data ──► CDR ──► Recovered Serial CLK (10 GHz) ──► Deserializer
                      └──► Recovered Parallel CLK (312.5 MHz) ──► RX FFE, DFE (÷32)
```

### 3.3 Rx Interface Specification

**Module**: `serdes_rx.sv`

| Port Name          | Direction | Width    | Type           | Description                       |
|--------------------|-----------|----------|----------------|-----------------------------------|
| `rx_analog_in`     | Input     | N/A      | `real`         | Analog Rx signal (from channel)   |
| `rst_n`            | Input     | 1        | `logic`        | Active-low reset                  |
| `rx_data_out`      | Output    | 32       | `logic`        | Parallel Rx data (recovered)      |
| `rx_data_valid`    | Output    | 1        | `logic`        | Data valid strobe                 |
| `modulation`       | Input     | 1        | `logic`        | 0 = NRZ, 1 = PAM4                 |
| `ctle_zero_freq`   | Input     | N/A      | `real`         | CTLE zero frequency (Hz)          |
| `ctle_pole1_freq`  | Input     | N/A      | `real`         | CTLE pole 1 frequency (Hz)        |
| `ctle_pole2_freq`  | Input     | N/A      | `real`         | CTLE pole 2 frequency (Hz)        |
| `ctle_dc_gain`     | Input     | N/A      | `real`         | CTLE DC gain (linear)             |
| `ffe_coeff_wr_en`  | Input     | 1        | `logic`        | RX FFE coefficient write enable   |
| `ffe_coeff_addr`   | Input     | 3        | `logic`        | RX FFE tap address                |
| `ffe_coeff_data`   | Input     | 10       | `logic signed` | RX FFE coefficient value          |
| `dfe_coeff_wr_en`  | Input     | 1        | `logic`        | DFE coefficient write enable      |
| `dfe_coeff_addr`   | Input     | 3        | `logic`        | DFE tap address                   |
| `dfe_coeff_data`   | Input     | 10       | `logic signed` | DFE coefficient value             |
| `dfe_threshold`    | Input     | 24       | `logic signed` | DFE slicer thresholds (3×8-bit)   |
| `cdr_locked`       | Output    | 1        | `logic`        | CDR lock indicator                |
| `rx_clk_out`       | Output    | 1        | `logic`        | Recovered parallel clock          |

---

## 4. Channel Model

### 4.1 Channel Characteristics

**Module**: `channel_model.sv` (optional for system-level testing)

- **Function**: Models lossy transmission medium (PCB trace, cable, connectors)
- **Effects Modeled**:
  - **Frequency-dependent attenuation**: Higher frequencies attenuated more (skin effect)
  - **Reflections**: Impedance mismatch at connectors
  - **Crosstalk**: Coupling between adjacent lanes (optional)
  - **Jitter**: Random and deterministic timing noise
- **Implementation**: FIR filter (impulse response) or frequency-domain model

### 4.2 Channel Insertion Loss

Typical PCIe channel loss at Nyquist frequency:

| Data Rate | Nyquist Freq | Typical Loss | Comments                  |
|-----------|--------------|--------------|---------------------------|
| 8 Gbps    | 4 GHz        | -15 to -20 dB| Gen3, moderate loss       |
| 16 Gbps   | 8 GHz        | -25 to -30 dB| Gen4, significant loss    |
| 32 Gbps   | 16 GHz       | -35 to -40 dB| Gen5 PAM4, severe loss    |

**Equalization Requirement**: CTLE + FFE + DFE must recover 20-40 dB of loss.

### 4.3 Channel Interface

| Port Name    | Direction | Width | Type   | Description                 |
|--------------|-----------|-------|--------|-----------------------------|
| `tx_signal`  | Input     | N/A   | `real` | Analog Tx signal (from DAC) |
| `rx_signal`  | Output    | N/A   | `real` | Analog Rx signal (to ADC)   |

---

## 5. Modulation Schemes

### 5.1 NRZ (Non-Return-to-Zero)

- **Levels**: 2 (binary)
- **Mapping**:
  - Bit `0` → -1.0 V (or -127 in digital)
  - Bit `1` → +1.0 V (or +127 in digital)
- **Symbol Rate**: Equal to bit rate (1 bit per symbol)
- **Bandwidth**: Nyquist frequency = Bit rate / 2
- **Use Case**: PCIe Gen3/Gen4, lower speeds (≤ 16 Gbps)

### 5.2 PAM4 (4-Level Pulse Amplitude Modulation)

- **Levels**: 4 (quaternary)
- **Mapping**:
  - Bits `00` → -0.75 V (or -96 in digital)
  - Bits `01` → -0.25 V (or -32 in digital)
  - Bits `10` → +0.25 V (or +32 in digital)
  - Bits `11` → +0.75 V (or +96 in digital)
- **Symbol Rate**: Half of bit rate (2 bits per symbol)
- **Bandwidth**: Nyquist frequency = Bit rate / 4 (half of NRZ)
- **Use Case**: PCIe Gen5/Gen6, high speeds (≥ 32 Gbps)

**Trade-off**: PAM4 uses half the bandwidth of NRZ but requires higher SNR (more sensitive to noise).

### 5.3 Modulation Selection Impact

| Aspect               | NRZ                          | PAM4                           |
|----------------------|------------------------------|--------------------------------|
| **Bandwidth**        | Higher (Nyquist = BR/2)      | Lower (Nyquist = BR/4)         |
| **SNR Requirement**  | Lower (~16 dB for BER 1e-12) | Higher (~26 dB for BER 1e-12)  |
| **Equalization**     | Simpler (2-level slicer)     | More complex (4-level slicer)  |
| **DFE Implementation**| Easier (binary feedback)    | Harder (multi-level feedback)  |
| **Channel Loss**     | Better tolerance             | Needs more equalization        |

---

## 6. Module Hierarchy and Dependencies

### 6.1 Directory Structure

```
rtl/
├── serdes_common.sv          # Common parameters, types, packages
├── tx/
│   ├── tx_ffe.sv             # Transmit FFE (pre-emphasis)
│   ├── serializer.sv         # Parallel-to-serial converter
│   ├── dac_model.sv          # DAC behavioral model
│   └── serdes_tx.sv          # Top-level Tx integrator
├── rx/
│   ├── adc_model.sv          # ADC behavioral model
│   ├── ctle_rnm.sv           # CTLE analog equalizer (RNM)
│   ├── rx_ffe.sv             # Receive FFE (7-tap)
│   ├── dfe.sv                # DFE (5-tap)
│   ├── cdr.sv                # Clock data recovery
│   ├── deserializer.sv       # Serial-to-parallel converter
│   └── serdes_rx.sv          # Top-level Rx integrator
├── channel/
│   └── channel_model.sv      # Transmission line model (optional)
└── modulation/
    ├── nrz_encoder.sv        # NRZ symbol mapping
    └── pam4_encoder.sv       # PAM4 symbol mapping

tb/
├── serdes_tx_tb.sv           # Tx-only testbench
├── serdes_rx_tb.sv           # Rx-only testbench
├── serdes_loopback_tb.sv     # Full Tx-Rx link testbench
└── pcie_compliance_tb.sv     # PCIe compliance tests
```

### 6.2 Module Instantiation Hierarchy

```
serdes_tx
├── nrz_encoder / pam4_encoder
├── tx_ffe
├── serializer
└── dac_model

serdes_rx
├── adc_model
├── ctle_rnm
├── rx_ffe
├── dfe
├── cdr
├── deserializer
└── nrz_encoder / pam4_encoder (for comparison)

serdes_loopback_tb
├── serdes_tx
├── channel_model
└── serdes_rx
```

### 6.3 Compilation Order (test_config.yaml)

For full system test:

```yaml
rtl_files:
  - serdes_common.sv          # 1. Common definitions first
  - modulation/nrz_encoder.sv # 2. Modulation helpers
  - modulation/pam4_encoder.sv
  - tx/tx_ffe.sv              # 3. Leaf modules
  - tx/serializer.sv
  - tx/dac_model.sv
  - rx/adc_model.sv
  - rx/ctle_rnm.sv
  - rx/rx_ffe.sv
  - rx/dfe.sv
  - rx/cdr.sv
  - rx/deserializer.sv
  - channel/channel_model.sv  # 4. Channel (uses nothing)
  - tx/serdes_tx.sv           # 5. Tx integrator (uses tx/*)
  - rx/serdes_rx.sv           # 6. Rx integrator (uses rx/*)
```

---

## 7. Common Definitions (serdes_common.sv)

### 7.1 Package Contents

```systemverilog
package serdes_pkg;

    // Data rate configurations
    typedef enum logic [1:0] {
        RATE_10GBPS  = 2'b00,  // 10 Gbps (PCIe Gen3)
        RATE_16GBPS  = 2'b01,  // 16 Gbps (PCIe Gen4)
        RATE_25GBPS  = 2'b10,  // 25 Gbps
        RATE_32GBPS  = 2'b11   // 32 Gbps (PCIe Gen5 PAM4)
    } data_rate_t;

    // Modulation types
    typedef enum logic {
        MODULATION_NRZ  = 1'b0,
        MODULATION_PAM4 = 1'b1
    } modulation_t;

    // NRZ symbol levels (8-bit signed)
    parameter logic signed [7:0] NRZ_LEVEL_0 = -8'sd128;  // Logic 0
    parameter logic signed [7:0] NRZ_LEVEL_1 =  8'sd127;  // Logic 1

    // PAM4 symbol levels (8-bit signed)
    parameter logic signed [7:0] PAM4_LEVEL_00 = -8'sd96;  // Symbol 00
    parameter logic signed [7:0] PAM4_LEVEL_01 = -8'sd32;  // Symbol 01
    parameter logic signed [7:0] PAM4_LEVEL_10 =  8'sd32;  // Symbol 10
    parameter logic signed [7:0] PAM4_LEVEL_11 =  8'sd96;  // Symbol 11

    // Analog voltage levels (for DAC/ADC models)
    parameter real ANALOG_VDD = 1.0;   // +1.0 V supply
    parameter real ANALOG_VSS = -1.0;  // -1.0 V supply

    // Clock frequencies (for reference)
    parameter real CLK_100MHZ   = 100.0e6;
    parameter real CLK_312_5MHZ = 312.5e6;  // Parallel clock for 10 Gbps
    parameter real CLK_10GHZ    = 10.0e9;   // Serial clock for 10 Gbps

endpackage : serdes_pkg
```

### 7.2 Common Type Definitions

```systemverilog
// Coefficient structure (for FFE/DFE)
typedef struct packed {
    logic        valid;
    logic [2:0]  addr;
    logic signed [9:0] value;
} coeff_t;

// Status/control interface
typedef struct packed {
    logic locked;      // CDR lock status
    logic error;       // Error indicator
    logic [7:0] ber;   // Bit error rate (if monitored)
} status_t;
```

---

## 8. Integration Considerations

### 8.1 Clock Domain Crossing (CDC)

**Challenge**: Tx and Rx operate on **different clocks** (Tx PLL vs. Rx CDR).

**CDC Locations**:
1. Between Tx parallel and serial clocks (handled in serializer)
2. Between Rx serial and parallel clocks (handled in deserializer)
3. Between Rx recovered clock and any external logic

**Solution**: Use proper CDC techniques:
- Dual-clock FIFOs for data
- Synchronizers (2-FF) for control signals
- Gray code for counters crossing domains

### 8.2 Reset Strategy

**Global Reset**: Asynchronous assert, synchronous de-assert per clock domain.

**Reset Sequence**:
1. Assert global `rst_n = 0` (asynchronous)
2. Wait ≥ 100 ns
3. De-assert `rst_n = 1` synchronously to each clock domain
4. Wait for PLL/CDR lock before data transmission

### 8.3 Calibration and Adaptation

**Tx Calibration**:
- Program TX FFE coefficients based on channel characterization
- Typically done once at link training (PCIe training sequence)

**Rx Adaptation**:
- **CTLE**: Set zero/pole frequencies for channel bandwidth
- **RX FFE**: Adapt coefficients using LMS or similar algorithm
- **DFE**: Adapt feedback taps to cancel post-cursor ISI
- **Adaptation Time**: ~1 ms typical (1e6 symbols @ 10 Gbps)

**Adaptation Algorithms** (future work, separate specification):
- See `spec/adaptation_algorithms.md` (to be created)

### 8.4 Performance Metrics

**Key Metrics to Monitor**:
1. **BER (Bit Error Rate)**: Target < 1e-12 for PCIe compliance
2. **Eye Height**: Vertical eye opening (mV), should be > 100 mV
3. **Eye Width**: Horizontal eye opening (ps), should be > 0.5 UI
4. **Jitter**: Total jitter < 0.3 UI RMS
5. **CDR Lock Time**: < 1000 UI typical

---

## 9. Simulation Strategy

### 9.1 Unit Tests (Individual Blocks)

Test each module in isolation:
- `tx_ffe_tb.sv`, `rx_ffe_tb.sv`, `dfe_tb.sv`, `ctle_rnm_tb.sv`
- Verify algorithm correctness, coefficient programming, saturation handling

**Simulation Time**: 10-100 µs per test

### 9.2 Integration Tests (Tx-only, Rx-only)

- **Tx-only**: `serdes_tx_tb.sv` → Verify Tx signal quality into ideal load
- **Rx-only**: `serdes_rx_tb.sv` → Verify Rx can recover known pattern with injected ISI

**Simulation Time**: 100-500 µs per test

### 9.3 System Tests (Full Link)

- **Loopback**: `serdes_loopback_tb.sv` → Full Tx-Channel-Rx simulation
- **BER Measurement**: Transmit PRBS pattern, compare Rx output, count errors
- **Eye Diagram**: Collect samples at UI boundaries, plot eye

**Simulation Time**: 1-10 ms (long for statistical BER measurement)

### 9.4 Compliance Tests

- **PCIe Compliance**: `pcie_compliance_tb.sv` → Verify TX/RX meet PCIe spec limits
  - Tx eye mask compliance
  - Rx jitter tolerance
  - Equalization coefficient ranges

**Simulation Time**: 10-100 ms (comprehensive sweep)

---

## 10. Future Enhancements

### 10.1 Phase 1 (Current Scope)

✅ FFE, DFE, CTLE specifications
✅ System architecture defined
✅ NRZ and PAM4 modulation

### 10.2 Phase 2 (Next Steps)

- Implement all RTL modules (`tx_ffe.sv`, `rx_ffe.sv`, `dfe.sv`, etc.)
- Create testbenches for unit and integration tests
- Validate against specifications

### 10.3 Phase 3 (Advanced Features)

- **Adaptive equalization algorithms**: LMS, RLS, look-up tables
- **CDR implementation**: Bang-bang phase detector, PI (phase interpolator)
- **PLL model**: With jitter injection for realistic simulation
- **Multi-lane support**: 4-lane or 8-lane SerDes (×4, ×8 PCIe)
- **Forward error correction (FEC)**: RS-FEC for Gen5/Gen6

### 10.4 Phase 4 (Synthesis and Validation)

- **FPGA implementation**: Xilinx or Intel FPGA prototyping
- **Hardware validation**: Real channel testing with test equipment
- **Performance optimization**: Timing closure, resource usage reduction

---

## 11. References

### 11.1 Standards
- **PCIe Base Specification** (v3.0/4.0/5.0/6.0): Complete SerDes requirements
- **IEEE 802.3**: Ethernet SerDes standards (10G/25G/100G)
- **OIF-CEI-03.0**: Common Electrical I/O Implementation Agreement

### 11.2 Books
- "High-Speed SerDes Devices and Applications" - Loi Chua
- "Jitter, Noise, and Signal Integrity at High-Speed" - Mike Peng Li

### 11.3 Related Documents
- `spec/ffe_specification.md` - FFE detailed specification
- `spec/dfe_specification.md` - DFE detailed specification
- `spec/ctle_specification.md` - CTLE detailed specification
- `spec/test_strategy.md` - Comprehensive test plan

---

## 12. Revision History

| Version | Date       | Author | Description                     |
|---------|------------|--------|---------------------------------|
| 1.0     | 2025-01-11 | Claude | Initial architecture definition |

---

**End of SerDes Architecture Specification**
