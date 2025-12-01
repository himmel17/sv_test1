# CTLE (Continuous-Time Linear Equalizer) 仕様書

**ドキュメントバージョン**: 1.0
**最終更新日**: 2025-01-11
**対象**: 高速SerDes (10-25 Gbps) PCIe Gen3/4/5向け
**モデリングアプローチ**: SystemVerilog Real Number Modeling (RNM)

---

## 1. 概要

### 1.1 目的

Continuous-Time Linear Equalizer (CTLE) は、受信機パスにおいてチャネルの周波数依存減衰を補償する**アナログ**ハイパスフィルタです。デジタル処理 (FFE/DFE) の前に高周波成分を増幅して信号完全性を回復します。

**主要な区別**: CTLEはFFE/DFEがデジタルであるのに対し、ADCの前の**アナログ領域** (連続時間) で動作します。

### 1.2 主な機能

- **アナログ動作モデル** SystemVerilog `real`型を使用
- **1個の零点、2個の極** による伝達関数 (業界標準)
- **プログラマブル周波数応答** 零点/極配置による
- **DC gainとpeaking制御** チャネル適応用
- **帯域幅: DCから15 GHz** (25 Gbps NRZ、50 Gbps PAM4をサポート)
- **Real Number Modeling (RNM)**: トランジスタレベル詳細なしの機能シミュレーション
- **PCIe準拠** の周波数応答特性

### 1.3 ブロック図

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
     clk ──>──┐   (オプション: 離散時間近似用)
    rst_n ──>─┘
```

---

## 2. インターフェース仕様

### 2.1 ポート定義

| ポート名         | 方向   | ビット幅 | 型     | 説明                                             |
|------------------|--------|----------|--------|--------------------------------------------------|
| `signal_in_p`    | Input  | N/A      | `real` | 差動入力正相 (0 ～ +1.0 V)                       |
| `signal_in_n`    | Input  | N/A      | `real` | 差動入力負相 (0 ～ +1.0 V)                       |
| `signal_out_p`   | Output | N/A      | `real` | 差動出力正相 (0 ～ +1.0 V)                       |
| `signal_out_n`   | Output | N/A      | `real` | 差動出力負相 (0 ～ +1.0 V)                       |
| `ctrl_zero_freq` | Input  | N/A      | `real` | 零点周波数 Hz単位 (ωz/2π)、例: 1.0e9 (1 GHz)    |
| `ctrl_pole1_freq`| Input  | N/A      | `real` | 第1極周波数 Hz単位 (ωp1/2π)、例: 5.0e9          |
| `ctrl_pole2_freq`| Input  | N/A      | `real` | 第2極周波数 Hz単位 (ωp2/2π)、例: 10.0e9         |
| `ctrl_dc_gain`   | Input  | N/A      | `real` | DC gain (線形、dBではない)、通常0.5 ～ 2.0       |
| `clk`            | Input  | 1        | `logic`| システムクロック (離散時間更新用、オプション)    |
| `rst_n`          | Input  | 1        | `logic`| Active-lowリセット (初期化用、オプション)        |

**注記:**
- **`real`型**: SystemVerilogの浮動小数点データ型 (64ビットIEEE 754倍精度)
- **差動信号**:
  - シングルエンド範囲: 信号あたり0 V ～ +1.0 V
  - 差動電圧: Vdiff = signal_in_p - signal_in_n (範囲: -1.0 V ～ +1.0 V)
  - 同相電圧: Vcm ≈ +0.5 V (典型的)
  - 理想的な差動動作を仮定 (完全な同相除去)
- 周波数は**Hz**で指定 (rad/sではない)
- DC gainは**線形スケール** (gain = 2.0は6 dBを意味)
- `clk`と`rst_n`は純粋な連続時間モデルではオプション

### 2.2 パラメータ定義

| パラメータ          | デフォルト | 範囲           | 説明                                            |
|---------------------|------------|----------------|-------------------------------------------------|
| `DEFAULT_ZERO_FREQ` | 1.0e9      | 0.5e9 - 5.0e9  | デフォルト零点周波数 (Hz) - boostを制御         |
| `DEFAULT_POLE1_FREQ`| 5.0e9      | 3.0e9 - 12.0e9 | デフォルト第1極 (Hz) - 高周波gainを制限         |
| `DEFAULT_POLE2_FREQ`| 10.0e9     | 8.0e9 - 20.0e9 | デフォルト第2極 (Hz) - 帯域幅超のロールオフ     |
| `DEFAULT_DC_GAIN`   | 1.0        | 0.3 - 3.0      | デフォルトDC gain (線形) - 全体振幅             |
| `PEAKING_DB_MAX`    | 12.0       | 6.0 - 20.0     | 最大peaking dB単位 (ピークでのgainを制限)       |
| `UPDATE_RATE`       | 1.0e12     | 1.0e9 - 1.0e15 | シミュレーション時間分解能 (Hz)、デフォルト1 ps |

**周波数計画ガイドライン:**
- Zero < Pole1 < Pole2 (単調な極零点配置)
- Pole1/Zero比: 通常3:1 ～ 10:1 (peakingを決定)
- 25 Gbps NRZ用: Zero ≈ 1-2 GHz, Pole1 ≈ 8-12 GHz
- PAM4用: より平坦な応答 (低いpeaking)

---

## 3. 機能説明

### 3.1 伝達関数

CTLEは**1次零点、2次極**の伝達関数を実装します：

```
H(s) = G × (1 + s/ωz) / [(1 + s/ωp1)(1 + s/ωp2)]
```

ここで：
- `G`: DC gain (無次元)
- `ωz = 2π × fz`: 零点角周波数 (rad/s)
- `ωp1 = 2π × fp1`: 第1極角周波数 (rad/s)
- `ωp2 = 2π × fp2`: 第2極角周波数 (rad/s)
- `s = jω`: 複素周波数 (Laplace変数)

**差動信号処理**:

伝達関数H(s)は**差動入力信号**に適用されます：

```
1. 差動からシングルエンド変換:
   signal_diff(t) = signal_in_p(t) - signal_in_n(t)

2. signal_diffに伝達関数H(s)を適用:
   signal_eq(t) = H(s)[signal_diff(t)]

3. シングルエンドから差動変換:
   signal_out_p(t) = Vcm + signal_eq(t) / 2
   signal_out_n(t) = Vcm - signal_eq(t) / 2

   ここでVcm = 0.5 V (同相電圧)
```

**主要な特性**:
- 同相信号 (両入力に等しく存在) は除去される (理想的CMRR = ∞)
- 差動モード信号のみがH(s)によって等化される
- 出力差動電圧: Vout_diff = signal_out_p - signal_out_n = signal_eq
- 出力同相電圧: (signal_out_p + signal_out_n) / 2 = Vcm = 0.5 V

### 3.2 周波数応答特性

#### 3.2.1 振幅応答

```
|H(jω)| = G × √(1 + (ω/ωz)²) / [√(1 + (ω/ωp1)²) × √(1 + (ω/ωp2)²)]
```

**領域**:
- **DC (ω → 0)**: `|H(0)| = G` (DC gain)
- **低周波 (ω < ωz)**: 平坦な応答 ≈ G
- **中間周波 (ωz < ω < ωp1)**: 上昇傾斜 ≈ +20 dB/decade (ハイパスブースト)
- **ピーク周波数 (ω ≈ ωp1)**: 最大gain (peaking)
- **高周波 (ω > ωp2)**: ロールオフ ≈ -20 dB/decade (2つの極が支配)

#### 3.2.2 Peaking計算

ピーク周波数におけるpeaking (dB単位):

```
Peaking (dB) = 20 × log10(|H(fpeak)| / G)
```

ここで`fpeak ≈ √(fz × fp1)` (零点と第1極の幾何平均)。

**設計ルール**: Peakingは典型的なチャネルに対して6-12 dBであるべき (高いpeaking = より積極的な等化)。

#### 3.2.3 位相応答 (参考情報)

```
∠H(jω) = arctan(ω/ωz) - arctan(ω/ωp1) - arctan(ω/ωp2)
```

位相応答は等化には**あまり重要ではない** (振幅が支配的) が、群遅延に影響する。

### 3.3 Real Number Modeling (RNM) 実装アプローチ

#### 3.3.1 連続時間モデル (理想的)

**純粋なアナログシミュレーション**用、微分方程式としてモデル化：

```
d²y/dt² + (ωp1 + ωp2) dy/dt + ωp1·ωp2·y = G·ωp1·ωp2 [dx/dt + ωz·x]
```

ここで`x = signal_in`, `y = signal_out`。

**実装上の課題**: SystemVerilogでODEを解く必要がある (複雑)。

#### 3.3.2 離散時間近似 (実用的)

**双線形変換** (Tustin法) を使用して連続伝達関数を離散化：

```
s → 2/T × (z-1)/(z+1)
```

ここで：
- `T = 1 / UPDATE_RATE`: サンプリング周期 (例: 1 ps = 1e-12 s)
- `z`: Z変換変数

**結果**: SystemVerilog `always @(posedge clk)`または`always @(signal_in)`で実装可能な差分方程式。

#### 3.3.3 簡略化1次近似 (v1.0推奨)

初期実装用、**カスケード1次セクション**を使用：

```
H(s) ≈ G × (1 + s/ωz) / (1 + s/ωp1) × 1/(1 + s/ωp2)
```

**2つのカスケードIIRフィルタ**として実装：
1. 零点-極ペア: `H1(s) = G × (1 + s/ωz) / (1 + s/ωp1)`
2. 追加極: `H2(s) = 1 / (1 + s/ωp2)`

**利点**: 各セクションは単純な1次IIR、実装と調整が容易。

---

## 4. 離散時間実装 (双線形変換)

### 4.1 1次セクション (零点-極ペア)

`H1(s) = G × (1 + s/ωz) / (1 + s/ωp1)`用：

**双線形変換**:
```
H1(z) = G × (b0 + b1·z⁻¹) / (1 - a1·z⁻¹)
```

**係数**:
```
T = 1 / UPDATE_RATE
Tz = 1 / (2 × ωz)
Tp1 = 1 / (2 × ωp1)

b0 = (T + 2·Tz) / (T + 2·Tp1)
b1 = (T - 2·Tz) / (T + 2·Tp1)
a1 = (T - 2·Tp1) / (T + 2·Tp1)

G_scaled = G × (T + 2·Tp1) / T  // Gain補正
```

**差分方程式**:
```
y1[n] = b0·x[n] + b1·x[n-1] + a1·y1[n-1]
```

### 4.2 2次セクション (追加極)

`H2(s) = 1 / (1 + s/ωp2)`用：

**双線形変換**:
```
H2(z) = c0 / (1 - a2·z⁻¹)
```

**係数**:
```
Tp2 = 1 / (2 × ωp2)

c0 = T / (T + 2·Tp2)
a2 = (T - 2·Tp2) / (T + 2·Tp2)
```

**差分方程式**:
```
y[n] = c0·y1[n] + a2·y[n-1]
```

### 4.3 カスケード実装

```
signal_in → [1次セクション] → intermediate → [極セクション] → signal_out
```

---

## 5. 周波数応答検証

### 5.1 Bode線図生成

**目的**: 振幅と位相応答が理論と一致することを検証。

**手順**:
1. 複数の周波数で正弦波入力でCTLEを刺激: 100 MHz, 500 MHz, 1 GHz, 2 GHz, 5 GHz, 10 GHz, 15 GHz
2. 各周波数`f`について：
   - `signal_in = A × sin(2π × f × t)`を印加、ここでA = 0.1 V
   - 定常状態出力振幅`B`を測定
   - Gainを計算: `Gain(dB) = 20 × log10(B / A)`
3. Gain対周波数をプロット (Bode振幅線図)
4. 理論的`|H(jω)|`と比較

**合格基準**:
- 測定gainが全周波数で理論値の±1 dB以内
- Peaking周波数が期待値の±10%以内
- Peaking振幅が±2 dB以内

### 5.2 主要周波数ポイント

典型的なCTLE (fz = 1 GHz, fp1 = 5 GHz, fp2 = 10 GHz, G = 1.0)用：

| 周波数 | 期待Gain | 説明                        |
|--------|----------|-----------------------------|
| 100 MHz| 0 dB     | DC gain (平坦領域)          |
| 1 GHz  | +1 dB    | 零点周波数 (ブースト開始)   |
| 3 GHz  | +6 dB    | ピーク周波数 (概算)         |
| 5 GHz  | +4 dB    | 第1極 (gainロールオフ)      |
| 10 GHz | 0 dB     | 第2極 (再び平坦)            |
| 15 GHz | -3 dB    | 帯域幅超                    |

---

## 6. テスト計画

### 6.1 単体テスト: DC応答

**目的**: DC gainがパラメータと一致することを検証。

**手順**:
1. `ctrl_dc_gain = 2.0` (6 dB) に設定
2. DC入力を印加: `signal_in = 0.5` (定数)
3. 整定を待つ (> 5時定数)
4. `signal_out`を測定

**期待結果**: `signal_out ≈ 1.0` (0.5 × 2.0)

**合格基準**: 出力が期待値の±2%以内。

### 6.2 単体テスト: 周波数スイープ (Bode線図)

**目的**: 完全な周波数応答を検証。

**手順**: (セクション5.1を参照)

**合格基準**: 全周波数ポイントが許容範囲内。

### 6.3 単体テスト: Peaking制御

**目的**: Peakingが極/零点比で調整されることを検証。

**手順**:
1. 構成1: fz = 1 GHz, fp1 = 10 GHz (比10:1) → 高いpeaking
2. 構成2: fz = 2 GHz, fp1 = 5 GHz (比2.5:1) → 低いpeaking
3. 両ケースでpeakingを測定

**期待結果**:
- 構成1: Peaking ≈ 12-15 dB
- 構成2: Peaking ≈ 4-6 dB

**合格基準**: 構成間のpeaking差 > 6 dB。

### 6.4 統合テスト: ステップ応答

**目的**: 時間領域動作を検証。

**手順**:
1. ステップ入力を印加: `signal_in = 0` → `signal_in = 1.0` at t = 1 ns
2. オーバーシュートと整定時間について`signal_out`を監視
3. 測定: ピーク値、整定時間 (最終値の2%以内)

**期待結果** (典型的CTLE用):
- オーバーシュート: 20-40% (ハイパス性質による)
- 整定時間: < 2 ns (高速応答)
- 最終値: ≈ `ctrl_dc_gain`

**合格基準**: オーバーシュート < 50%、整定時間 < 5 ns。

### 6.5 統合テスト: PRBSパターン等化

**目的**: CTLEが現実的なデータに対してアイ開口を改善することを検証。

**手順**:
1. 減衰PRBS7パターンを生成 (損失の多いチャネルをシミュレート)
2. 最適化設定でCTLEを通す
3. CTLE前後のアイ高さを測定

**期待結果**:
- CTLE前のアイ高さ: < 0.3 V (70%閉じている)
- CTLE後のアイ高さ: > 0.7 V (30%開いている)

**合格基準**: アイ高さ改善 > 2倍 (6 dB)。

### 6.6 ストレステスト: パラメータスイープ

**目的**: パラメータ範囲全体で安定性を確保。

**手順**:
1. `ctrl_zero_freq`をスイープ: 0.5 GHz ～ 5 GHz (10ステップ)
2. `ctrl_pole1_freq`をスイープ: 3 GHz ～ 12 GHz (10ステップ)
3. 各組み合わせで5 GHz正弦波を印加
4. 数値不安定性 (NaN, Inf) をチェック

**合格基準**: 全パラメータ組み合わせで出力にNaNまたはInfなし。

### 6.7 差動テスト: 差動バランス

**目的**: 差動出力バランスと同相電圧を検証。

**手順**:
1. DC差動入力を印加: `signal_in_p = 0.6 V`, `signal_in_n = 0.4 V` (差動 = 0.2 V)
2. 整定を待つ (> 5時定数)
3. `signal_out_p`と`signal_out_n`を測定
4. 計算:
   - 差動出力: `Vout_diff = signal_out_p - signal_out_n`
   - 同相出力: `Vout_cm = (signal_out_p + signal_out_n) / 2`

**期待結果**:
- `Vout_diff ≈ ctrl_dc_gain × 0.2 V` (差動gainが適用される)
- `Vout_cm ≈ 0.5 V` (同相電圧が保持される)
- `signal_out_p + signal_out_n ≈ 1.0 V` (合計 = 2 × Vcm)

**合格基準**:
- Vout_diffが期待値の±5%以内
- Vout_cmが0.5 Vの±0.02 V以内

### 6.8 差動テスト: 同相除去

**目的**: 理想的な同相除去 (CMRR = ∞) を検証。

**手順**:
1. 同相のみの入力を印加: `signal_in_p = signal_in_n = 0.7 V` (差動なし)
2. 整定を待つ
3. `signal_out_p`と`signal_out_n`を測定
4. 差動出力を計算: `Vout_diff = signal_out_p - signal_out_n`

**期待結果**:
- `Vout_diff ≈ 0 V` (同相入力に対して差動出力なし)
- `signal_out_p ≈ signal_out_n ≈ 0.5 V` (出力は同相電圧)

**合格基準**:
- |Vout_diff| < 0.001 V (同相入力に対して差動 < 1 mV)
- 両出力が0.5 Vの±0.02 V以内

---

## 7. SystemVerilog実装ノート

### 7.1 モジュール宣言テンプレート

```systemverilog
`timescale 1ns / 1ps

// Continuous-Time Linear Equalizer (CTLE) - Analog RNM
// Real Number Modelingによる動作シミュレーション

module ctle_rnm #(
    parameter real DEFAULT_ZERO_FREQ  = 1.0e9,   // 1 GHz
    parameter real DEFAULT_POLE1_FREQ = 5.0e9,   // 5 GHz
    parameter real DEFAULT_POLE2_FREQ = 10.0e9,  // 10 GHz
    parameter real DEFAULT_DC_GAIN    = 1.0,     // Unity gain
    parameter real UPDATE_RATE        = 1.0e12,  // 1 THz (1 ps分解能)
    parameter real CM_VOLTAGE         = 0.5      // 同相電圧 (V)
)(
    input  real  signal_in_p,      // 差動入力正相 (0-1.0 V)
    input  real  signal_in_n,      // 差動入力負相 (0-1.0 V)
    output real  signal_out_p,     // 差動出力正相 (0-1.0 V)
    output real  signal_out_n,     // 差動出力負相 (0-1.0 V)
    input  real  ctrl_zero_freq,   // 零点周波数 (Hz)
    input  real  ctrl_pole1_freq,  // 極1周波数 (Hz)
    input  real  ctrl_pole2_freq,  // 極2周波数 (Hz)
    input  real  ctrl_dc_gain,     // DC gain (線形)
    input  logic clk,              // オプション: 離散時間クロック
    input  logic rst_n             // オプション: リセット
);

    // 内部状態変数 (離散時間IIR用)
    real x_prev;          // 以前の入力
    real y1_prev;         // 以前の第1セクション出力
    real y_prev;          // 以前の最終出力

    // フィルタ係数 (パラメータ変更時に再計算)
    real b0, b1, a1;      // 第1セクション (零点-極)
    real c0, a2;          // 第2セクション (極のみ)

    // ... 実装 ...

endmodule
```

### 7.2 主要実装ガイドライン

#### 7.2.1 係数計算 (パラメータ変更時)

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

    // 第1セクション係数
    b0 = (T + 2.0*Tz) / (T + 2.0*Tp1);
    b1 = (T - 2.0*Tz) / (T + 2.0*Tp1);
    a1 = (T - 2.0*Tp1) / (T + 2.0*Tp1);

    // 第2セクション係数
    c0 = T / (T + 2.0*Tp2);
    a2 = (T - 2.0*Tp2) / (T + 2.0*Tp2);
endfunction
```

#### 7.2.2 離散時間フィルタ更新

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

        // ステップ1: 差動からシングルエンド変換
        signal_diff = signal_in_p - signal_in_n;

        // ステップ2: 差動信号にフィルタを適用
        // 第1セクション (零点-極ペア)
        y1 = b0 * signal_diff + b1 * x_prev + a1 * y1_prev;

        // 第2セクション (追加極)
        y = c0 * y1 + a2 * y_prev;

        // DC gainを適用
        signal_eq = ctrl_dc_gain * y;

        // ステップ3: シングルエンドから差動変換
        signal_out_p <= CM_VOLTAGE + signal_eq / 2.0;
        signal_out_n <= CM_VOLTAGE - signal_eq / 2.0;

        // 状態更新
        x_prev  <= signal_diff;
        y1_prev <= y1;
        y_prev  <= y;
    end
end
```

#### 7.2.3 連続時間代替 (イベント駆動)

**連続時間**シミュレーション用 (クロックなし)：

```systemverilog
always @(signal_in or ctrl_zero_freq or ctrl_pole1_freq or
         ctrl_pole2_freq or ctrl_dc_gain) begin

    // パラメータ変更時に再計算
    if ($time > 0) begin  // 初期化グリッチを回避
        calculate_coefficients();
    end

    // フィルタを適用 (イベント駆動向けの簡略化)
    // 注記: 真の連続時間には積分が必要、これは近似
    real delta_t = $realtime - last_update_time;

    // ... (簡略化1次応答) ...

    last_update_time = $realtime;
end
```

**注記**: イベント駆動アプローチはRNMのクロック化離散時間より**精度が低い**。

### 7.3 合成考慮事項

**重要**: CTLE RNMは**合成不可** (`real`型を使用)。

**目的**: 以下の動作シミュレーションのみ：
- アルゴリズム検証
- システムレベルSerDesシミュレーション
- アナログブロックのテストベンチモデリング

**FPGA/ASIC実装用**: 実際のアナログ回路または固定小数点デジタル近似に置き換える。

### 7.4 検証フック

```systemverilog
`ifdef SIMULATION
    // デバッグ: 検証用に係数をエクスポート
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

## 8. テストベンチ要件

### 8.1 テストベンチモジュールテンプレート

```systemverilog
`timescale 1ns / 1ps

module ctle_rnm_tb #(
    parameter SIM_TIMEOUT = 50000  // 50 µs
);

    // クロック生成 (離散時間モデル用)
    logic clk = 0;
    always #0.5 clk = ~clk;  // 1 THz (1 ps周期) - UPDATE_RATEに一致

    // DUT信号
    logic rst_n;
    real  signal_in_p, signal_in_n;
    real  signal_out_p, signal_out_n;
    real  ctrl_zero_freq;
    real  ctrl_pole1_freq;
    real  ctrl_pole2_freq;
    real  ctrl_dc_gain;

    // DUTインスタンス化
    ctle_rnm #(
        .DEFAULT_ZERO_FREQ(1.0e9),
        .DEFAULT_POLE1_FREQ(5.0e9),
        .DEFAULT_POLE2_FREQ(10.0e9),
        .DEFAULT_DC_GAIN(1.0),
        .UPDATE_RATE(1.0e12),
        .CM_VOLTAGE(0.5)
    ) dut (.*);

    // VCDダンプ
    initial begin
        $dumpfile("sim/waves/ctle_rnm.vcd");
        $dumpvars(0, ctle_rnm_tb);
    end

    // ヘルパータスク: 差動正弦波を印加してgainを測定
    task measure_gain(input real freq_hz, output real gain_db);
        real amplitude_in, amplitude_out;
        real period, duration;
        int cycles;
        real cm_voltage = 0.5;  // 同相電圧

        begin
            amplitude_in = 0.1;  // 100 mV差動振幅
            period = 1.0e9 / freq_hz;  // 周期 ns単位
            cycles = 10;  // 平均化サイクル数
            duration = cycles * period;

            // 差動正弦波を印加
            for (real t = 0; t < duration; t = t + 0.001) begin  // 1 psステップ
                real signal_diff = amplitude_in * $sin(2.0 * 3.14159 * freq_hz * t * 1.0e-9);
                signal_in_p = cm_voltage + signal_diff / 2.0;
                signal_in_n = cm_voltage - signal_diff / 2.0;
                #0.001;  // 1 ps待機
            end

            // 差動出力振幅を測定 (簡略化: 定常状態を仮定)
            real signal_out_diff = signal_out_p - signal_out_n;
            amplitude_out = /* ... signal_out_diffのpeak-to-peak / 2を測定 ... */;
            gain_db = 20.0 * $log10(amplitude_out / amplitude_in);
        end
    endtask

    // テストシーケンス
    int error_count = 0;
    initial begin
        rst_n = 0;
        signal_in_p = 0.5;  // 同相電圧
        signal_in_n = 0.5;  // 差動信号なし
        ctrl_zero_freq = 1.0e9;
        ctrl_pole1_freq = 5.0e9;
        ctrl_pole2_freq = 10.0e9;
        ctrl_dc_gain = 1.0;

        #10 rst_n = 1;

        // テスト1: DC応答 (セクション6.1を参照)
        // テスト2: 周波数スイープ (セクション6.2を参照)
        // ...

        if (error_count == 0) begin
            $display("*** PASSED: All CTLE tests passed successfully ***");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
        end
        $finish;
    end

    // タイムアウトウォッチドッグ
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout");
        $finish;
    end

endmodule
```

### 8.2 テスト構成 (test_config.yaml)

```yaml
- name: ctle_rnm
  enabled: true
  description: "CTLEアナログ等化 Real Number Modelingを使用"
  top_module: ctle_rnm_tb
  testbench_file: ctle_rnm_tb.sv
  rtl_files:
    - ctle_rnm.sv
  verilator_extra_flags:
    - --trace-underscore
  sim_timeout: "50us"
```

**Verilator注記**: Verilatorはシミュレーション用に`real`型をサポート (合成不可)。

---

## 9. 参考文献

### 9.1 標準規格
- **PCIe Base Specification** (v3.0/4.0/5.0): アナログ等化要件
- **IEEE 802.3**: Ethernet CTLE仕様

### 9.2 書籍
- Razavi, "Design of Analog CMOS Integrated Circuits" (イコライザに関する章)
- Lee, "The Design of CMOS Radio-Frequency Integrated Circuits" (伝達関数解析)

### 9.3 アプリケーションノート
- "Understanding CTLE for High-Speed Links" - Keysight Technologies
- "Modeling Analog Behavior in SystemVerilog" - Mentor Graphics

### 9.4 関連ドキュメント
- `spec/ffe_specification.md` - Feed-Forward Equalizer
- `spec/dfe_specification.md` - Decision Feedback Equalizer
- `spec/serdes_architecture.md` - システムレベルSerDesアーキテクチャ

---

## 10. 改訂履歴

| バージョン | 日付       | 作成者 | 説明                     |
|------------|------------|--------|--------------------------|
| 1.0        | 2025-01-11 | Claude | 初版仕様書作成           |

---

## 付録A: 周波数応答例

### 例1: 高Peaking構成 (積極的等化)

**パラメータ**:
- fz = 1 GHz, fp1 = 10 GHz, fp2 = 15 GHz
- DC gain = 0.7 (高peakingで出力を範囲内に保つため)

**期待される応答**:
- Peaking周波数: √(1 × 10) ≈ 3.2 GHz
- Peaking振幅: ≈ +12 dB
- 使用例: 長く損失の多いチャネル (ナイキストで>30 dB損失)

### 例2: 平坦な応答 (低Peaking、PAM4)

**パラメータ**:
- fz = 2 GHz, fp1 = 6 GHz, fp2 = 12 GHz
- DC gain = 1.0

**期待される応答**:
- Peaking周波数: √(2 × 6) ≈ 3.5 GHz
- Peaking振幅: ≈ +4 dB
- 使用例: 短いチャネル、PAM4変調 (より平坦な応答が必要)

### 例3: 最大帯域幅 (高速リンク)

**パラメータ**:
- fz = 3 GHz, fp1 = 12 GHz, fp2 = 20 GHz
- DC gain = 1.2

**期待される応答**:
- Peaking周波数: √(3 × 12) ≈ 6 GHz
- Peaking振幅: ≈ +8 dB
- 使用例: 25+ Gbps SerDes、広い帯域幅が重要

---

## 付録B: 双線形変換導出

**連続時間伝達関数**:
```
H(s) = (b_s × s + b_0) / (s + a_0)
```

**双線形変換** (s → z領域):
```
s = (2/T) × (z - 1) / (z + 1)
```

**代入と簡略化**:
```
H(z) = [b_s × (2/T) × (z-1)/(z+1) + b_0] / [(2/T) × (z-1)/(z+1) + a_0]

分子と分母にT(z+1)を乗算:

H(z) = [2×b_s×(z-1) + b_0×T×(z+1)] / [2×(z-1) + a_0×T×(z+1)]
     = [(2×b_s + b_0×T)×z + (-2×b_s + b_0×T)] / [(2 + a_0×T)×z + (-2 + a_0×T)]
```

**先頭係数で割って正規化**:
```
H(z) = [B0 + B1×z⁻¹] / [1 - A1×z⁻¹]
```

ここで：
```
B0 = (2×b_s + b_0×T) / (2 + a_0×T)
B1 = (-2×b_s + b_0×T) / (2 + a_0×T)
A1 = -(−2 + a_0×T) / (2 + a_0×T) = (2 - a_0×T) / (2 + a_0×T)
```

**差分方程式**:
```
y[n] = B0×x[n] + B1×x[n-1] + A1×y[n-1]
```

---

**CTLE仕様書 終わり**
