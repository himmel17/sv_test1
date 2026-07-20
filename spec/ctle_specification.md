# CTLE (Continuous-Time Linear Equalizer) Specification

**Document Version**: 1.1
**Last Updated**: 2026-07-20
**Target**: High-Speed SerDes (10-25 Gbps) for PCIe Gen3/4/5
**Modeling Approach**: SystemVerilog Real Number Modeling (RNM)

---

## 1. Overview

### 1.1 Purpose

The Continuous-Time Linear Equalizer (CTLE) is an **analog** high-pass filter in the receiver path that compensates for channel frequency-dependent attenuation. It amplifies high-frequency components to restore signal integrity before digital processing (FFE/DFE).

**Key Distinction**: CTLE operates in the **analog domain** (continuous-time) before the ADC, unlike FFE/DFE which are digital.

### 1.2 Key Features

- **Analog behavioral model** using SystemVerilog `real` type
- **Single zero, two poles** transfer function (industry standard)
- **Programmable frequency response** via zero/pole placement
- **DC gain and peaking control** for channel adaptation
- **Bandwidth: DC to 15 GHz** (supports 25 Gbps NRZ, 50 Gbps PAM4)
- **Real Number Modeling (RNM)**: Functional simulation without transistor-level details
- **PCIe-compliant** frequency response characteristics

### 1.3 Block Diagram

```
signal_in_p ──────┐
(real, 0-1.0V)    │  ┌──────────────────────────────────┐
                  ├─►│                                  │  signal_out_p
signal_in_n ──────┘  │   CTLE (Analog Equalizer)        ├──────────────►
(real, 0-1.0V)       │   Differential Input/Output      │  (real, 0-1.0V)
 Differential        │                                  │
 from channel        │   Internal Processing:           │  signal_out_n
                     │   1. Diff→Single: Vin_diff       ├──────────────►
                     │   2. Transfer Function H(s)      │  (real, 0-1.0V)
                     │   3. Single→Diff conversion      │   Equalized
                     │                                  │   differential
                     │   H(s) = G × (1+s/ωz)            │   (to ADC)
                     │            ──────────────          │
                     │            (1+s/ωp1)(1+s/ωp2)    │
                     │                                  │
                     │   Programmable Parameters:       │
ctrl_zero_freq       │   - Zero frequency (ωz)          │
─────────────────────┤   - Pole1 frequency (ωp1)        │
ctrl_pole1_freq      │   - Pole2 frequency (ωp2)        │
─────────────────────┤   - DC gain (G)                  │
ctrl_pole2_freq      │                                  │
─────────────────────┤                                  │
ctrl_dc_gain         │                                  │
─────────────────────┤                                  │
                     └──────────────────────────────────┘
     clk ──>──┐   (Optional: for discrete-time approximation)
    rst_n ──>─┘
```

---

## 2. Interface Specification

### 2.1 Port Definitions

| Port Name        | Direction | Width | Type    | Description                                        |
|------------------|-----------|-------|---------|----------------------------------------------------|
| `signal_in_p`    | Input     | N/A   | `real`  | Differential input positive (0 to +1.0 V)          |
| `signal_in_n`    | Input     | N/A   | `real`  | Differential input negative (0 to +1.0 V)          |
| `signal_out_p`   | Output    | N/A   | `real`  | Differential output positive (0 to +1.0 V)         |
| `signal_out_n`   | Output    | N/A   | `real`  | Differential output negative (0 to +1.0 V)         |
| `ctrl_zero_freq` | Input     | N/A   | `real`  | Zero frequency in Hz (ωz/2π), e.g., 1.0e9 (1 GHz)  |
| `ctrl_pole1_freq`| Input     | N/A   | `real`  | First pole frequency in Hz (ωp1/2π), e.g., 5.0e9   |
| `ctrl_pole2_freq`| Input     | N/A   | `real`  | Second pole frequency in Hz (ωp2/2π), e.g., 10.0e9 |
| `ctrl_dc_gain`   | Input     | N/A   | `real`  | DC gain (linear, not dB), typically 0.5 to 2.0     |
| `clk`            | Input     | 1     | `logic` | System clock (for discrete-time update, optional)  |
| `rst_n`          | Input     | 1     | `logic` | Active-low reset (optional, for initialization)    |

**Notes:**
- **`real` type**: SystemVerilog's floating-point data type (64-bit IEEE 754 double precision)
- **Differential signaling**:
  - Single-ended range: 0 V to +1.0 V per signal
  - Differential voltage: Vdiff = signal_in_p - signal_in_n (range: -1.0 V to +1.0 V)
  - Common-mode voltage: Vcm ≈ +0.5 V (typical)
  - Ideal differential operation assumed (perfect common-mode rejection)
- Frequencies specified in **Hz** (not rad/s)
- DC gain is **linear scale** (gain = 2.0 means 6 dB)
- `clk` and `rst_n` are optional for pure continuous-time models

### 2.2 Parameter Definitions

| Parameter           | Default | Range          | Description                                     |
|---------------------|---------|----------------|-------------------------------------------------|
| `DEFAULT_ZERO_FREQ` | 1.0e9   | 0.5e9 - 5.0e9  | Default zero frequency (Hz) - controls boost    |
| `DEFAULT_POLE1_FREQ`| 5.0e9   | 3.0e9 - 12.0e9 | Default first pole (Hz) - limits high-freq gain |
| `DEFAULT_POLE2_FREQ`| 10.0e9  | 8.0e9 - 20.0e9 | Default second pole (Hz) - rolloff beyond BW    |
| `DEFAULT_DC_GAIN`   | 1.0     | 0.3 - 3.0      | Default DC gain (linear) - overall amplitude    |
| `PEAKING_DB_MAX`    | 12.0    | 6.0 - 20.0     | Maximum peaking in dB (limits gain at peak)     |
| `UPDATE_RATE`       | 1.0e12  | 1.0e9 - 1.0e15 | Simulation time resolution (Hz), 1 ps default   |

**Frequency Planning Guidelines:**
- Zero < Pole1 < Pole2 (monotonic pole-zero placement)
- Pole1/Zero ratio: 3:1 to 10:1 typical (determines peaking)
- For 25 Gbps NRZ: Zero ≈ 1-2 GHz, Pole1 ≈ 8-12 GHz
- For PAM4: Flatter response (lower peaking)

---

## 3. Functional Description

### 3.1 Transfer Function

The CTLE implements a **first-order zero, second-order pole** transfer function:

```
H(s) = G × (1 + s/ωz) / [(1 + s/ωp1)(1 + s/ωp2)]
```

Where:
- `G`: DC gain (dimensionless)
- `ωz = 2π × fz`: Zero angular frequency (rad/s)
- `ωp1 = 2π × fp1`: First pole angular frequency (rad/s)
- `ωp2 = 2π × fp2`: Second pole angular frequency (rad/s)
- `s = jω`: Complex frequency (Laplace variable)

**Differential Signal Processing**:

The transfer function H(s) is applied to the **differential input signal**:

```
1. Differential to single-ended conversion:
   signal_diff(t) = signal_in_p(t) - signal_in_n(t)

2. Apply transfer function H(s) to signal_diff:
   signal_eq(t) = H(s)[signal_diff(t)]

3. Single-ended to differential conversion:
   signal_out_p(t) = Vcm + signal_eq(t) / 2
   signal_out_n(t) = Vcm - signal_eq(t) / 2

   Where Vcm = 0.5 V (common-mode voltage)
```

**Key Properties**:
- Common-mode signals (present equally on both inputs) are rejected (ideal CMRR = ∞)
- Only differential-mode signals are equalized by H(s)
- Output differential voltage: Vout_diff = signal_out_p - signal_out_n = signal_eq
- Output common-mode voltage: (signal_out_p + signal_out_n) / 2 = Vcm = 0.5 V

### 3.2 Frequency Response Characteristics

#### 3.2.1 Magnitude Response

```
|H(jω)| = G × √(1 + (ω/ωz)²) / [√(1 + (ω/ωp1)²) × √(1 + (ω/ωp2)²)]
```

**Regions**:
- **DC (ω → 0)**: `|H(0)| = G` (DC gain)
- **Low frequency (ω < ωz)**: Flat response ≈ G
- **Mid frequency (ωz < ω < ωp1)**: Rising slope ≈ +20 dB/decade (high-pass boost)
- **Peak frequency (ω ≈ ωp1)**: Maximum gain (peaking)
- **High frequency (ω > ωp2)**: Rolling off ≈ -20 dB/decade (two poles dominate)

#### 3.2.2 Peaking Calculation

Peaking (in dB) at the peak frequency:

```
Peaking (dB) = 20 × log10(|H(fpeak)| / G)
```

Where `fpeak ≈ √(fz × fp1)` (geometric mean of zero and first pole).

**Design Rule**: Peaking should be 6-12 dB for typical channels (higher peaking = more aggressive equalization).

#### 3.2.3 Phase Response (Informational)

```
∠H(jω) = arctan(ω/ωz) - arctan(ω/ωp1) - arctan(ω/ωp2)
```

Phase response is **less critical** for equalization (magnitude dominates), but affects group delay.

### 3.3 Real Number Modeling (RNM) Implementation Approach

#### 3.3.1 Continuous-Time Model (Ideal)

For **pure analog simulation**, model as differential equation:

```
d²y/dt² + (ωp1 + ωp2) dy/dt + ωp1·ωp2·y = G·ωp1·ωp2 [dx/dt + ωz·x]
```

Where `x = signal_in`, `y = signal_out`.

**Implementation Challenge**: Requires solving ODEs in SystemVerilog (complex).

#### 3.3.2 Discrete-Time Approximation (Practical)

Use **bilinear transform** (Tustin's method) to convert continuous transfer function to discrete:

```
s → 2/T × (z-1)/(z+1)
```

Where:
- `T = 1 / UPDATE_RATE`: Sampling period (e.g., 1 ps = 1e-12 s)
- `z`: Z-transform variable

**Result**: Difference equation implementable in SystemVerilog `always @(posedge clk)` or `always @(signal_in)`.

#### 3.3.3 Simplified First-Order Approximation (Recommended for v1.0)

For initial implementation, use **cascaded first-order sections**:

```
H(s) ≈ G × (1 + s/ωz) / (1 + s/ωp1) × 1/(1 + s/ωp2)
```

Implemented as **two cascaded IIR filters**:
1. Zero-pole pair: `H1(s) = G × (1 + s/ωz) / (1 + s/ωp1)`
2. Additional pole: `H2(s) = 1 / (1 + s/ωp2)`

**Benefit**: Each section is simple first-order IIR, easier to implement and tune.

---

## 4. Discrete-Time Implementation (Bilinear Transform)

### 4.1 First-Order Section (Zero-Pole Pair)

For `H1(s) = G × (1 + s/ωz) / (1 + s/ωp1)`:

**Bilinear transform**:
```
H1(z) = G × (b0 + b1·z⁻¹) / (1 - a1·z⁻¹)
```

**Coefficients**:
```
T = 1 / UPDATE_RATE
Tz = 1 / (2 × ωz)
Tp1 = 1 / (2 × ωp1)

b0 = (T + 2·Tz) / (T + 2·Tp1)
b1 = (T - 2·Tz) / (T + 2·Tp1)
a1 = (T - 2·Tp1) / (T + 2·Tp1)

G_scaled = G × (T + 2·Tp1) / T  // Gain correction
```

**Difference Equation**:
```
y1[n] = b0·x[n] + b1·x[n-1] + a1·y1[n-1]
```

### 4.2 Second-Order Section (Additional Pole)

For `H2(s) = 1 / (1 + s/ωp2)`:

**Bilinear transform**:
```
H2(z) = c0 / (1 - a2·z⁻¹)
```

**Coefficients**:
```
Tp2 = 1 / (2 × ωp2)

c0 = T / (T + 2·Tp2)
a2 = (T - 2·Tp2) / (T + 2·Tp2)
```

**Difference Equation**:
```
y[n] = c0·y1[n] + a2·y[n-1]
```

### 4.3 Cascaded Implementation

```
signal_in → [First-order section] → intermediate → [Pole section] → signal_out
```

---

## 5. Frequency Response Verification

### 5.1 Verification Strategy (Layered)

The CTLE model is a discrete-time LTI IIR filter. Implementation correctness and specification conformance are therefore verified in **separate layers**, so that any failure can be attributed unambiguously:

| Layer | What It Verifies | Method | Runs On |
|-------|------------------|--------|---------|
| 1. Coefficient check | Coefficient calculation (b0, b1, a1, c0, a2) | Export coefficients via debug hooks (Section 7.4), compare with Python reference (`scipy.signal.bilinear`) | SV sim + Python |
| 2. Sample-exact match | Difference equation implemented exactly as intended | Apply an impulse input, compare **every output sample** with `scipy.signal.lfilter` | SV sim + Python |
| 3. Discretization conformance | H(z) adequately approximates analog H(s) | Pure Python analysis: `scipy.signal.freqz` of H(z) vs. theoretical \|H(jω)\| | Python only |
| 4. Self-checking smoke test | End-to-end sanity with framework pass/fail | Sine sweep at 3-5 frequencies with lock-in detection, compared against **H(z)** | SV testbench |

**Rationale**:
- Layers 1-2 establish that the SystemVerilog implementation equals the intended difference equation (sample-exact, reusing the `scripts/verify_noise_match_batch.py` workflow).
- Layer 3 judges the bilinear discretization against the analog specification **without any additional SystemVerilog simulation**.
- Layer 4 exists because the test framework requires a self-contained, self-checking testbench. It is a smoke test, not the primary conformance check.

### 5.2 Theoretical Reference: H(z), Not H(s)

Simulation output must be compared against the **discrete-time** transfer function actually implemented:

```
H_ref(f) = H(z) evaluated at z = exp(j·2π·f·T),   T = 1 / UPDATE_RATE
```

The bilinear transform warps frequencies as `ω_analog = (2/T) × tan(ω·T/2)`. With T = 1 ps the warping error is below 0.1% up to 15 GHz — negligible against a ±1 dB tolerance — but using H(z) as the reference cleanly separates "implementation bug" (Layers 1-2) from "discretization error" (Layer 3).

### 5.3 Gain/Phase Measurement: Lock-in Detection (Layer 4)

Peak-picking on discrete output samples is sensitive to residual transients and to the sampling grid. Use **lock-in detection (single-bin DFT)** instead:

1. Apply differential sine `signal_diff = A × sin(2π × f × t)`, A = 0.1 V
2. Discard the settling interval (slowest time constant ≈ 1/(2π × 1 GHz) ≈ 160 ps; discarding 5 cycles + 2 ns is more than sufficient)
3. Over an **integer number of cycles** (≥ 20), accumulate:
   - `I = Σ y[n] × sin(2π·f·t_n)`
   - `Q = Σ y[n] × cos(2π·f·t_n)`
4. Amplitude `B = (2/N) × √(I² + Q²)`, phase `φ = atan2(Q, I)`
5. `Gain(dB) = 20 × log10(B / A)`

Phase and group delay come at no extra cost — record them as informational data.

**Test frequency placement**: Log-spaced points clustered around fz, fpeak ≈ √(fz × fp1), fp1, and fp2 (where the response slope is steepest) are more informative than an evenly spread fixed list. For the Layer 4 smoke test, 3-5 points are sufficient (e.g., 0.5 GHz, 3 GHz, 10 GHz).

**Pass Criteria (Layer 4)**:
- Measured gain within ±1 dB of the H(z) reference at all smoke-test frequencies
- (Peaking frequency/magnitude conformance is judged in Layer 3 — see Section 6.2.3)

### 5.4 Key Frequency Points

For typical CTLE (fz = 1 GHz, fp1 = 5 GHz, fp2 = 10 GHz, G = 1.0):

| Frequency | Expected Gain | Description              |
|-----------|---------------|--------------------------|
| 100 MHz   | 0 dB          | DC gain (flat region)    |
| 1 GHz     | +1 dB         | Zero frequency (start boost) |
| 3 GHz     | +6 dB         | Peak frequency (approx)  |
| 5 GHz     | +4 dB         | First pole (gain rolloff)|
| 10 GHz    | 0 dB          | Second pole (flat again) |
| 15 GHz    | -3 dB         | Beyond bandwidth         |

---

## 6. Test Plan

### 6.1 Unit Test: DC Response

**Objective**: Verify DC gain matches parameter.

**Procedure**:
1. Set `ctrl_dc_gain = 2.0` (6 dB)
2. Apply DC input: `signal_in = 0.5` (constant)
3. Wait for settling (> 5 time constants)
4. Measure `signal_out`

**Expected**: `signal_out ≈ 1.0` (0.5 × 2.0)

**Pass Criteria**: Output within ±2% of expected.

### 6.2 Unit Test: Frequency Response (Layered Verification)

**Objective**: Validate the complete frequency response using the layered strategy of Section 5.1.

#### 6.2.1 Layer 1: Coefficient Verification

**Procedure**:
1. Run simulation with default parameters; dump b0, b1, a1, c0, a2 via debug hooks (Section 7.4)
2. Compute reference coefficients in Python (`scipy.signal.bilinear`)
3. Compare

**Pass Criteria**: All coefficients match within 1e-12 relative error.

#### 6.2.2 Layer 2: Impulse-Response Sample-Exact Match

**Procedure**:
1. Apply a single-sample differential impulse (e.g., 0.2 V for one UPDATE_RATE period, 0 V elsewhere)
2. Capture ≥ 2048 output samples from the VCD
3. Run the identical input through `scipy.signal.lfilter` with the reference coefficients
4. Compare sample-by-sample (workflow follows `scripts/verify_noise_match_batch.py`)

**Pass Criteria**: Maximum absolute error < 1e-12 V (floating-point rounding only).

#### 6.2.3 Layer 3: Discretization Conformance (Python Only)

**Procedure**:
1. Evaluate H(z) with `scipy.signal.freqz` at log-spaced frequencies from 100 MHz to 15 GHz
2. Compare against theoretical |H(jω)| (Section 3.2.1); generate a Bode plot for documentation

**Pass Criteria**:
- |H(z)| within ±1 dB of |H(jω)| from 100 MHz to 15 GHz
- Peaking frequency within ±10% of expected, peaking magnitude within ±2 dB

No SystemVerilog simulation is required for this layer.

#### 6.2.4 Layer 4: Sine-Sweep Smoke Test (Self-Checking Testbench)

**Procedure**:
1. In the testbench, measure gain at 3-5 frequencies (e.g., 0.5, 3, 10 GHz) using lock-in detection (Section 5.3)
2. Compare against precomputed H(z) reference values

**Pass Criteria**: Within ±1 dB at all smoke-test frequencies; the testbench reports `*** PASSED ***` / `*** FAILED ***`.

### 6.3 Unit Test: Peaking Control

**Objective**: Verify peaking adjusts with pole/zero ratio.

**Procedure**:
1. Configuration 1: fz = 1 GHz, fp1 = 10 GHz (ratio 10:1) → High peaking
2. Configuration 2: fz = 2 GHz, fp1 = 5 GHz (ratio 2.5:1) → Low peaking
3. Measure peaking in both cases

**Expected**:
- Config 1: Peaking ≈ 12-15 dB
- Config 2: Peaking ≈ 4-6 dB

**Pass Criteria**: Peaking difference > 6 dB between configurations.

**Note**: Peaking values are obtained cheaply from the Layer 3 Python analysis (Section 6.2.3); in-simulation measurement uses lock-in detection (Section 5.3).

### 6.4 Integration Test: Step Response

**Objective**: Verify time-domain behavior.

**Procedure**:
1. Apply step input: `signal_in = 0` → `signal_in = 1.0` at t = 1 ns
2. Monitor `signal_out` for overshoot and settling time
3. Measure: Peak value, settling time (to within 2% of final)

**Expected** (for typical CTLE):
- Overshoot: 20-40% (due to high-pass nature)
- Settling time: < 2 ns (fast response)
- Final value: ≈ `ctrl_dc_gain`

**Pass Criteria**: Overshoot < 50%, settling time < 5 ns.

### 6.5 Integration Test: PRBS Pattern Equalization

**Objective**: Verify CTLE improves eye opening for realistic data.

**Procedure**:
1. Generate attenuated PRBS7 pattern (simulate lossy channel)
2. Feed through CTLE with optimized settings
3. Measure eye height before and after CTLE

**Expected**:
- Eye height before CTLE: < 0.3 V (70% closed)
- Eye height after CTLE: > 0.7 V (30% open)

**Pass Criteria**: Eye height improvement > 2× (6 dB).

### 6.6 Stress Test: Parameter Sweep

**Objective**: Ensure stability across parameter ranges.

**Procedure**:
1. Sweep `ctrl_zero_freq`: 0.5 GHz to 5 GHz (10 steps)
2. Sweep `ctrl_pole1_freq`: 3 GHz to 12 GHz (10 steps)
3. For each combination, apply 5 GHz sine wave
4. Check for numerical instability (NaN, Inf)

**Pass Criteria**: No NaN or Inf in output for all parameter combinations.

### 6.7 Differential Test: Differential Balance

**Objective**: Verify differential output balance and common-mode voltage.

**Procedure**:
1. Apply DC differential input: `signal_in_p = 0.6 V`, `signal_in_n = 0.4 V` (differential = 0.2 V)
2. Wait for settling (> 5 time constants)
3. Measure `signal_out_p` and `signal_out_n`
4. Calculate:
   - Differential output: `Vout_diff = signal_out_p - signal_out_n`
   - Common-mode output: `Vout_cm = (signal_out_p + signal_out_n) / 2`

**Expected**:
- `Vout_diff ≈ ctrl_dc_gain × 0.2 V` (differential gain applied)
- `Vout_cm ≈ 0.5 V` (common-mode voltage preserved)
- `signal_out_p + signal_out_n ≈ 1.0 V` (sum equals 2 × Vcm)

**Pass Criteria**:
- Vout_diff within ±5% of expected
- Vout_cm within ±0.02 V of 0.5 V

### 6.8 Differential Test: Common-Mode Rejection

**Objective**: Verify ideal common-mode rejection (CMRR = ∞).

**Procedure**:
1. Apply common-mode-only input: `signal_in_p = signal_in_n = 0.7 V` (no differential)
2. Wait for settling
3. Measure `signal_out_p` and `signal_out_n`
4. Calculate differential output: `Vout_diff = signal_out_p - signal_out_n`

**Expected**:
- `Vout_diff ≈ 0 V` (no differential output for common-mode input)
- `signal_out_p ≈ signal_out_n ≈ 0.5 V` (outputs at common-mode voltage)

**Pass Criteria**:
- |Vout_diff| < 0.001 V (< 1 mV differential for common-mode input)
- Both outputs within ±0.02 V of 0.5 V

---

## 7. SystemVerilog Implementation Notes

### 7.1 Module Declaration Template

```systemverilog
`timescale 1ps / 1fs  // High-speed SerDes domain (per project timescale guidelines)

// Continuous-Time Linear Equalizer (CTLE) - Analog RNM
// Real Number Modeling for behavioral simulation

module ctle_rnm #(
    parameter real DEFAULT_ZERO_FREQ  = 1.0e9,   // 1 GHz
    parameter real DEFAULT_POLE1_FREQ = 5.0e9,   // 5 GHz
    parameter real DEFAULT_POLE2_FREQ = 10.0e9,  // 10 GHz
    parameter real DEFAULT_DC_GAIN    = 1.0,     // Unity gain
    parameter real UPDATE_RATE        = 1.0e12,  // 1 THz (1 ps resolution)
    parameter real CM_VOLTAGE         = 0.5      // Common-mode voltage (V)
)(
    input  real  signal_in_p,      // Differential input positive (0-1.0 V)
    input  real  signal_in_n,      // Differential input negative (0-1.0 V)
    output real  signal_out_p,     // Differential output positive (0-1.0 V)
    output real  signal_out_n,     // Differential output negative (0-1.0 V)
    input  real  ctrl_zero_freq,   // Zero frequency (Hz)
    input  real  ctrl_pole1_freq,  // Pole 1 frequency (Hz)
    input  real  ctrl_pole2_freq,  // Pole 2 frequency (Hz)
    input  real  ctrl_dc_gain,     // DC gain (linear)
    input  logic clk,              // Optional: discrete-time clock
    input  logic rst_n             // Optional: reset
);

    // Internal state variables (for discrete-time IIR)
    real x_prev;          // Previous input
    real y1_prev;         // Previous first section output
    real y_prev;          // Previous final output

    // Filter coefficients (recalculated when parameters change)
    real b0, b1, a1;      // First section (zero-pole)
    real c0, a2;          // Second section (pole only)

    // ... implementation ...

endmodule
```

### 7.2 Key Implementation Guidelines

#### 7.2.1 Coefficient Calculation (On Parameter Change)

```systemverilog
real T, Tz, Tp1, Tp2;
real omega_z, omega_p1, omega_p2;

function void calculate_coefficients();
    T = 1.0 / UPDATE_RATE;

    omega_z  = 2.0 * 3.14159265359 * ctrl_zero_freq;
    omega_p1 = 2.0 * 3.14159265359 * ctrl_pole1_freq;
    omega_p2 = 2.0 * 3.14159265359 * ctrl_pole2_freq;

    Tz  = 1.0 / (2.0 * omega_z);
    Tp1 = 1.0 / (2.0 * omega_p1);
    Tp2 = 1.0 / (2.0 * omega_p2);

    // First section coefficients
    b0 = (T + 2.0*Tz) / (T + 2.0*Tp1);
    b1 = (T - 2.0*Tz) / (T + 2.0*Tp1);
    a1 = (T - 2.0*Tp1) / (T + 2.0*Tp1);

    // Second section coefficients
    c0 = T / (T + 2.0*Tp2);
    a2 = (T - 2.0*Tp2) / (T + 2.0*Tp2);
endfunction
```

#### 7.2.2 Discrete-Time Filter Update

```systemverilog
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        x_prev      <= 0.0;
        y1_prev     <= 0.0;
        y_prev      <= 0.0;
        signal_out_p <= CM_VOLTAGE;
        signal_out_n <= CM_VOLTAGE;
        calculate_coefficients();
    end else begin
        real signal_diff, y1, y, signal_eq;

        // Step 1: Differential to single-ended conversion
        signal_diff = signal_in_p - signal_in_n;

        // Step 2: Apply filter to differential signal
        // First section (zero-pole pair)
        y1 = b0 * signal_diff + b1 * x_prev + a1 * y1_prev;

        // Second section (additional pole)
        y = c0 * y1 + a2 * y_prev;

        // Apply DC gain
        signal_eq = ctrl_dc_gain * y;

        // Step 3: Single-ended to differential conversion
        signal_out_p <= CM_VOLTAGE + signal_eq / 2.0;
        signal_out_n <= CM_VOLTAGE - signal_eq / 2.0;

        // Update state
        x_prev  <= signal_diff;
        y1_prev <= y1;
        y_prev  <= y;
    end
end
```

#### 7.2.3 Continuous-Time Alternative (Event-Driven)

For **continuous-time** simulation (no clock):

```systemverilog
always @(signal_in or ctrl_zero_freq or ctrl_pole1_freq or
         ctrl_pole2_freq or ctrl_dc_gain) begin

    // Recalculate on parameter change
    if ($time > 0) begin  // Avoid initialization glitch
        calculate_coefficients();
    end

    // Apply filter (simplified for event-driven)
    // Note: True continuous-time requires integration, this is approximation
    real delta_t = $realtime - last_update_time;

    // ... (simplified first-order response) ...

    last_update_time = $realtime;
end
```

**Note**: Event-driven approach is **less accurate** than clocked discrete-time for RNM.

### 7.3 Synthesis Considerations

**Important**: CTLE RNM is **NOT synthesizable** (uses `real` type).

**Purpose**: Behavioral simulation only, for:
- Algorithm verification
- System-level SerDes simulation
- Testbench modeling of analog blocks

**For FPGA/ASIC implementation**: Replace with actual analog circuit or fixed-point digital approximation.

### 7.4 Verification Hooks

```systemverilog
`ifdef SIMULATION
    // Debug: Export coefficients for verification
    real debug_b0, debug_b1, debug_a1;
    real debug_c0, debug_a2;
    real debug_y1, debug_y;

    assign debug_b0 = b0;
    assign debug_b1 = b1;
    assign debug_a1 = a1;
    assign debug_c0 = c0;
    assign debug_a2 = a2;
    assign debug_y1 = y1_prev;
    assign debug_y  = y_prev;
`endif
```

---

## 8. Testbench Requirements

### 8.1 Testbench Module Template

```systemverilog
`timescale 1ps / 1fs  // Time unit 1 ps: matches UPDATE_RATE = 1.0e12 (1 ps period)

module ctle_rnm_tb #(
    parameter SIM_TIMEOUT = 50_000_000  // 50 µs (time unit = 1 ps)
);

    // Clock generation (for discrete-time model)
    logic clk = 0;
    always #0.5 clk = ~clk;  // 1 ps period (1 THz) - matches UPDATE_RATE = 1.0e12

    // DUT signals
    logic rst_n;
    real  signal_in_p, signal_in_n;
    real  signal_out_p, signal_out_n;
    real  ctrl_zero_freq;
    real  ctrl_pole1_freq;
    real  ctrl_pole2_freq;
    real  ctrl_dc_gain;

    // DUT instantiation
    ctle_rnm #(
        .DEFAULT_ZERO_FREQ(1.0e9),
        .DEFAULT_POLE1_FREQ(5.0e9),
        .DEFAULT_POLE2_FREQ(10.0e9),
        .DEFAULT_DC_GAIN(1.0),
        .UPDATE_RATE(1.0e12),
        .CM_VOLTAGE(0.5)
    ) dut (.*);

    // VCD dump
    initial begin
        $dumpfile("sim/waves/ctle_rnm.vcd");
        $dumpvars(0, ctle_rnm_tb);
    end

    // Helper task: lock-in (single-bin DFT) gain/phase measurement (Section 5.3)
    task automatic measure_gain_lockin(
        input  real freq_hz,
        output real gain_db,
        output real phase_deg
    );
        real PI = 3.14159265358979;
        real amplitude_in, amplitude_out;
        real period_ps, settle_ps, meas_ps, t_ps;
        real signal_diff, out_diff;
        real acc_i, acc_q;   // In-phase / quadrature accumulators
        int  n_samples;
        begin
            amplitude_in = 0.1;                       // 100 mV differential amplitude
            period_ps    = 1.0e12 / freq_hz;          // Period in ps
            settle_ps    = 5.0 * period_ps + 2000.0;  // Settling: 5 cycles + 2 ns
            meas_ps      = 20.0 * period_ps;          // Integrate over 20 full cycles
            acc_i = 0.0; acc_q = 0.0; n_samples = 0;

            for (t_ps = 0.0; t_ps < settle_ps + meas_ps; t_ps += 1.0) begin  // 1 ps steps
                signal_diff = amplitude_in * $sin(2.0 * PI * freq_hz * t_ps * 1.0e-12);
                signal_in_p = 0.5 + signal_diff / 2.0;
                signal_in_n = 0.5 - signal_diff / 2.0;
                #1.0;  // 1 ps = 1 / UPDATE_RATE
                if (t_ps >= settle_ps) begin
                    out_diff = signal_out_p - signal_out_n;
                    acc_i += out_diff * $sin(2.0 * PI * freq_hz * t_ps * 1.0e-12);
                    acc_q += out_diff * $cos(2.0 * PI * freq_hz * t_ps * 1.0e-12);
                    n_samples++;
                end
            end

            // Note: residual spectral leakage from a non-integer number of
            // samples per cycle is negligible for the ±1 dB smoke-test tolerance
            amplitude_out = 2.0 * $sqrt(acc_i*acc_i + acc_q*acc_q) / n_samples;
            gain_db   = 20.0 * $log10(amplitude_out / amplitude_in);
            phase_deg = $atan2(acc_q, acc_i) * 180.0 / PI;  // Informational
        end
    endtask

    // Test sequence
    int error_count = 0;
    initial begin
        rst_n = 0;
        signal_in_p = 0.5;  // Common-mode voltage
        signal_in_n = 0.5;  // No differential signal
        ctrl_zero_freq = 1.0e9;
        ctrl_pole1_freq = 5.0e9;
        ctrl_pole2_freq = 10.0e9;
        ctrl_dc_gain = 1.0;

        #100 rst_n = 1;  // 100 ps

        // Test 1: DC response (see section 6.1)
        // Test 2: Layer 4 sine-sweep smoke test (see section 6.2.4)
        //         using measure_gain_lockin() at 3-5 frequencies vs. H(z) reference
        // Note: Layers 1-3 (coefficient / sample-exact / discretization checks)
        //       run offline in Python (see sections 6.2.1-6.2.3 and 8.3)
        // ...

        if (error_count == 0) begin
            $display("*** PASSED: All CTLE tests passed successfully ***");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
        end
        $finish;
    end

    // Timeout watchdog
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout");
        $finish;
    end

endmodule
```

### 8.2 Test Configuration (test_config.yaml)

```yaml
- name: ctle_rnm
  enabled: true
  description: "CTLE analog equalization with Real Number Modeling"
  top_module: ctle_rnm_tb
  testbench_file: ctle_rnm_tb.sv
  rtl_files:
    - ctle_rnm.sv
  verilator_extra_flags:
    - --trace-underscore
  sim_timeout: "50us"
```

**Verilator Note**: Verilator supports `real` types for simulation (no synthesis).

### 8.3 Python Verification Scripts (Layers 1-3)

Following the flicker-noise batch verification workflow (`scripts/verify_noise_match_batch.py`), a companion script `scripts/verify_ctle_match.py` (to be implemented alongside the RTL) performs:

1. **Layer 1**: Compute reference coefficients with `scipy.signal.bilinear` and compare against the debug-hook values (Section 7.4) dumped by the simulation
2. **Layer 2**: Extract the impulse response from `sim/waves/ctle_rnm.vcd` (via `vcdvcd`) and compare sample-by-sample against `scipy.signal.lfilter`
3. **Layer 3**: Evaluate H(z) with `scipy.signal.freqz`, check it against the theoretical |H(jω)|, and emit a Bode plot for documentation

---

## 9. References

### 9.1 Standards
- **PCIe Base Specification** (v3.0/4.0/5.0): Analog equalization requirements
- **IEEE 802.3**: Ethernet CTLE specifications

### 9.2 Books
- Razavi, "Design of Analog CMOS Integrated Circuits" (Chapter on equalizers)
- Lee, "The Design of CMOS Radio-Frequency Integrated Circuits" (Transfer function analysis)

### 9.3 Application Notes
- "Understanding CTLE for High-Speed Links" - Keysight Technologies
- "Modeling Analog Behavior in SystemVerilog" - Mentor Graphics

### 9.4 Related Documents
- `spec/ffe_specification.md` - Feed-Forward Equalizer
- `spec/dfe_specification.md` - Decision Feedback Equalizer
- `spec/serdes_architecture.md` - System-level SerDes architecture

---

## 10. Revision History

| Version | Date       | Author | Description                     |
|---------|------------|--------|---------------------------------|
| 1.0     | 2025-01-11 | Claude | Initial specification creation  |
| 1.1     | 2026-07-20 | Claude | Layered frequency-response verification strategy (Sections 5, 6.2, 8.3); testbench/RTL timescale corrected to `1ps/1fs`; lock-in measurement task |

---

## Appendix A: Frequency Response Examples

### Example 1: High Peaking Configuration (Aggressive Equalization)

**Parameters**:
- fz = 1 GHz, fp1 = 10 GHz, fp2 = 15 GHz
- DC gain = 0.7 (to keep output in range with high peaking)

**Expected Response**:
- Peaking frequency: √(1 × 10) ≈ 3.2 GHz
- Peaking magnitude: ≈ +12 dB
- Use case: Long, lossy channels (>30 dB loss at Nyquist)

### Example 2: Flat Response (Low Peaking, PAM4)

**Parameters**:
- fz = 2 GHz, fp1 = 6 GHz, fp2 = 12 GHz
- DC gain = 1.0

**Expected Response**:
- Peaking frequency: √(2 × 6) ≈ 3.5 GHz
- Peaking magnitude: ≈ +4 dB
- Use case: Short channels, PAM4 modulation (needs flatter response)

### Example 3: Maximum Bandwidth (High-Speed Links)

**Parameters**:
- fz = 3 GHz, fp1 = 12 GHz, fp2 = 20 GHz
- DC gain = 1.2

**Expected Response**:
- Peaking frequency: √(3 × 12) ≈ 6 GHz
- Peaking magnitude: ≈ +8 dB
- Use case: 25+ Gbps SerDes, wide bandwidth critical

---

## Appendix B: Bilinear Transform Derivation

**Continuous-Time Transfer Function**:
```
H(s) = (b_s × s + b_0) / (s + a_0)
```

**Bilinear Transform** (s → z domain):
```
s = (2/T) × (z - 1) / (z + 1)
```

**Substitution and Simplification**:
```
H(z) = [b_s × (2/T) × (z-1)/(z+1) + b_0] / [(2/T) × (z-1)/(z+1) + a_0]

Multiply numerator and denominator by T(z+1):

H(z) = [2×b_s×(z-1) + b_0×T×(z+1)] / [2×(z-1) + a_0×T×(z+1)]
     = [(2×b_s + b_0×T)×z + (-2×b_s + b_0×T)] / [(2 + a_0×T)×z + (-2 + a_0×T)]
```

**Normalize by dividing by leading coefficient**:
```
H(z) = [B0 + B1×z⁻¹] / [1 - A1×z⁻¹]
```

Where:
```
B0 = (2×b_s + b_0×T) / (2 + a_0×T)
B1 = (-2×b_s + b_0×T) / (2 + a_0×T)
A1 = -(−2 + a_0×T) / (2 + a_0×T) = (2 - a_0×T) / (2 + a_0×T)
```

**Difference Equation**:
```
y[n] = B0×x[n] + B1×x[n-1] + A1×y[n-1]
```

---

**End of CTLE Specification**
