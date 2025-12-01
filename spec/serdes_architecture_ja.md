# SerDesアーキテクチャ仕様書

**ドキュメントバージョン**: 1.0
**最終更新日**: 2025-01-11
**対象**: 高速SerDes (10-25 Gbps) PCIe Gen3/4/5向け
**変調方式**: NRZ, PAM4

---

## 1. システム概要

### 1.1 目的

本ドキュメントは、高速シリアルデータ送受信のための**完全なSerDes (Serializer/Deserializer) システムアーキテクチャ**を定義します。送信機 (Tx)、受信機 (Rx)、等化ブロック (FFE, DFE, CTLE)、およびアナログインターフェース (DAC, ADC) を統合的なシステムに統合します。

### 1.2 主なシステム機能

- **データレート**: 10-25 Gbps/レーン
- **変調方式**: NRZ (2レベル), PAM4 (4レベル)
- **送信機**: DACベースのアナログ出力、FFEプリエンファシス付き
- **受信機**: ADCベースのサンプリング、CTLE + FFE + DFE等化カスケード付き
- **標準準拠**: PCIe Gen3/4/5
- **等化**: 適応型送信および受信等化
- **クロックアーキテクチャ**: Tx PLL + Rx CDR (Clock Data Recovery)

### 1.3 トップレベルブロック図

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

## 2. 送信機 (Tx) アーキテクチャ

### 2.1 Txデータパス

**フロー**: `パラレルデータ → TX FFE → Serializer → DAC → アナログ信号 → Channel`

#### 2.1.1 パラレルデータ入力

- **ビット幅**: 32ビットパラレル (10 Gbpsの場合: 32ビット @ 312.5 MHz = 10 Gbpsシリアル)
- **フォーマット**:
  - **NRZ**: 1ビット/シンボル → 32シンボル/クロック
  - **PAM4**: 2ビット/シンボル → 16シンボル/クロック (32ビット / 2)
- **エンコーディング**: 上流でプリエンコード済み (8b/10bまたは128b/130b) (SerDesスコープ外)

#### 2.1.2 TX FFE (プリエンファシス)

**モジュール**: `tx_ffe.sv` (`spec/ffe_specification.md`を参照)

- **目的**: 既知のチャネル損失を事前補償するためにTx信号を事前歪み
- **構成**: 通常3-7タップ (Rx FFEより少ない)
- **係数**: チャネル特性評価に基づいてプログラム
- **出力**: プリエンファシス済みパラレルデータ (まだデジタル)

#### 2.1.3 Serializer (パラレル→シリアル)

**モジュール**: `serializer.sv`

- **機能**: 32ビットパラレルを高速1ビットシリアルに変換
- **クロックドメイン**:
  - 入力: パラレルクロック (例: 10 Gbpsで312.5 MHz)
  - 出力: シリアルクロック (例: 10 Gbpsで10 GHz)
- **実装**: クロック逓倍付きシフトレジスタ

#### 2.1.4 DAC (Digital-to-Analog Converter)

**モジュール**: `dac_model.sv` (シミュレーション用の動作モデル)

- **機能**: シリアルデジタルビットをアナログ電圧レベルに変換
- **変調マッピング**:
  - **NRZ**:
    - `0` → -1.0 V (論理0)
    - `1` → +1.0 V (論理1)
  - **PAM4**:
    - `00` → -0.75 V (シンボル0)
    - `01` → -0.25 V (シンボル1)
    - `10` → +0.25 V (シンボル2)
    - `11` → +0.75 V (シンボル3)
- **出力タイプ**: `real` (RNMシミュレーション用のアナログ電圧)

### 2.2 Txクロックアーキテクチャ

#### 2.2.1 PLL (Phase-Locked Loop)

**モジュール**: `pll_model.sv` (動作モデル)

- **入力**: リファレンスクロック (例: 100 MHz水晶)
- **出力**: 高速シリアルクロック (例: 10 Gbps NRZで10 GHz)
- **逓倍率**: 10 Gbpsで100倍、25 Gbpsで250倍
- **ジッタ**: < 1 ps RMS (PCIe準拠用)

#### 2.2.2 クロック分配

```
REF_CLK (100 MHz) ──► PLL ──► Serial CLK (10 GHz) ──► Serializer
                           └──► Parallel CLK (312.5 MHz) ──► TX FFE (÷32)
```

### 2.3 Txインターフェース仕様

**モジュール**: `serdes_tx.sv`

| ポート名           | 方向   | ビット幅 | 型             | 説明                                |
|--------------------|--------|----------|----------------|-------------------------------------|
| `ref_clk`          | Input  | 1        | `logic`        | リファレンスクロック (例: 100 MHz)  |
| `rst_n`            | Input  | 1        | `logic`        | Active-lowリセット                  |
| `tx_data_in`       | Input  | 32       | `logic`        | パラレルTxデータ (NRZまたはPAM4)    |
| `tx_data_valid`    | Input  | 1        | `logic`        | データ有効ストローブ                |
| `modulation`       | Input  | 1        | `logic`        | 0 = NRZ, 1 = PAM4                   |
| `ffe_coeff_wr_en`  | Input  | 1        | `logic`        | FFE係数書き込みイネーブル           |
| `ffe_coeff_addr`   | Input  | 3        | `logic`        | FFEタップアドレス                   |
| `ffe_coeff_data`   | Input  | 10       | `logic signed` | FFE係数値                           |
| `tx_analog_out`    | Output | N/A      | `real`         | アナログTx信号 (チャネルへ)         |
| `tx_clk_out`       | Output | 1        | `logic`        | パラレルクロック出力 (同期用)       |

---

## 3. 受信機 (Rx) アーキテクチャ

### 3.1 Rxデータパス

**フロー**: `アナログ信号 → ADC → CTLE → RX FFE → DFE → Deserializer → パラレルデータ`

#### 3.1.1 ADC (Analog-to-Digital Converter)

**モジュール**: `adc_model.sv` (動作モデル)

- **機能**: アナログRx信号をシリアルレートでサンプリングし、8ビットデジタルに変換
- **分解能**: 8ビット (256レベル、PAM4 + ノイズマージンに十分)
- **サンプリングレート**: シリアルレート (例: 10 Gbpsで10 GS/s)
- **入力タイプ**: `real` (チャネルからのアナログ電圧)
- **出力タイプ**: `logic [7:0]` (符号付き、-128 ～ +127)
- **量子化**:
  - アナログ範囲 [-1.0 V, +1.0 V] をデジタル [-128, +127] にマップ
  - ADC_out = clamp(round(analog_in × 128), -128, 127)

#### 3.1.2 CTLE (Continuous-Time Linear Equalizer)

**モジュール**: `ctle_rnm.sv` (`spec/ctle_specification.md`を参照)

- **目的**: ADC前のアナログハイパス等化 (高周波をブースト)
- **実装**: `real`型を使用したReal Number Modeling (RNM)
- **配置**: 実際のハードウェアでは通常**ADC前**だが、シミュレーションでは簡略化のためADC後に配置可能
- **構成**: チャネル適応のためのプログラマブル零点/極周波数

**シミュレーション注記**: 実装の容易さのため、CTLEはADC後に配置してよく、8ビットサンプルを`real`に変換してフィルタリングし、再び`logic [7:0]`に戻す。

#### 3.1.3 RX FFE (7タップFeed-Forward Equalizer)

**モジュール**: `rx_ffe.sv` (`spec/ffe_specification.md`を参照)

- **目的**: デジタル化信号の線形等化 (残留ISIを除去)
- **構成**: 7タップ (Tx FFEより多く、より細かい制御)
- **入力**: 8ビットADCサンプル (またはCTLE出力)
- **出力**: 8ビット等化済みサンプル

#### 3.1.4 DFE (5タップDecision Feedback Equalizer)

**モジュール**: `dfe.sv` (`spec/dfe_specification.md`を参照)

- **目的**: 過去の判定を使用した非線形等化 (post-cursor ISIをキャンセル)
- **構成**: 5フィードバックタップ
- **入力**: RX FFEからの等化済みサンプル
- **出力**: 検出シンボル (硬判定: NRZレベルまたはPAM4レベル)

#### 3.1.5 Deserializer (シリアル→パラレル)

**モジュール**: `deserializer.sv`

- **機能**: シリアルビットストリームを32ビットパラレルワードに変換
- **クロックドメイン**:
  - 入力: 回復シリアルクロック (CDRから)
  - 出力: パラレルクロック (シリアルクロック ÷ 32)
- **実装**: デマルチプレクシング付きシフトレジスタ

### 3.2 Rxクロックアーキテクチャ

#### 3.2.1 CDR (Clock Data Recovery)

**モジュール**: `cdr.sv` (動作モデル)

- **機能**: 入力データストリームからクロックを抽出 (別のクロックラインなし)
- **アルゴリズム**: Phase-locked loop (PLL) + 位相検出器
- **入力**: 等化済みデータストリーム (DFEまたはFFEから)
- **出力**:
  - `recovered_clk`: シリアルレートクロック (例: 10 GHz)
  - `clk_locked`: ロック指示 (CDRがデータクロックを獲得)
- **ロック時間**: 通常約1000 UI (unit interval)

#### 3.2.2 クロック分配

```
Incoming Data ──► CDR ──► Recovered Serial CLK (10 GHz) ──► Deserializer
                      └──► Recovered Parallel CLK (312.5 MHz) ──► RX FFE, DFE (÷32)
```

### 3.3 Rxインターフェース仕様

**モジュール**: `serdes_rx.sv`

| ポート名           | 方向   | ビット幅 | 型             | 説明                                |
|--------------------|--------|----------|----------------|-------------------------------------|
| `rx_analog_in`     | Input  | N/A      | `real`         | アナログRx信号 (チャネルから)       |
| `rst_n`            | Input  | 1        | `logic`        | Active-lowリセット                  |
| `rx_data_out`      | Output | 32       | `logic`        | パラレルRxデータ (回復済み)         |
| `rx_data_valid`    | Output | 1        | `logic`        | データ有効ストローブ                |
| `modulation`       | Input  | 1        | `logic`        | 0 = NRZ, 1 = PAM4                   |
| `ctle_zero_freq`   | Input  | N/A      | `real`         | CTLE零点周波数 (Hz)                 |
| `ctle_pole1_freq`  | Input  | N/A      | `real`         | CTLEポール1周波数 (Hz)              |
| `ctle_pole2_freq`  | Input  | N/A      | `real`         | CTLEポール2周波数 (Hz)              |
| `ctle_dc_gain`     | Input  | N/A      | `real`         | CTLE DC gain (線形)                 |
| `ffe_coeff_wr_en`  | Input  | 1        | `logic`        | RX FFE係数書き込みイネーブル        |
| `ffe_coeff_addr`   | Input  | 3        | `logic`        | RX FFEタップアドレス                |
| `ffe_coeff_data`   | Input  | 10       | `logic signed` | RX FFE係数値                        |
| `dfe_coeff_wr_en`  | Input  | 1        | `logic`        | DFE係数書き込みイネーブル           |
| `dfe_coeff_addr`   | Input  | 3        | `logic`        | DFEタップアドレス                   |
| `dfe_coeff_data`   | Input  | 10       | `logic signed` | DFE係数値                           |
| `dfe_threshold`    | Input  | 24       | `logic signed` | DFEスライサー閾値 (3×8ビット)       |
| `cdr_locked`       | Output | 1        | `logic`        | CDRロック指示                       |
| `rx_clk_out`       | Output | 1        | `logic`        | 回復パラレルクロック                |

---

## 4. チャネルモデル

### 4.1 チャネル特性

**モジュール**: `channel_model.sv` (システムレベルテスト用オプション)

- **機能**: 損失のある伝送媒体をモデル化 (PCBトレース、ケーブル、コネクタ)
- **モデル化される効果**:
  - **周波数依存減衰**: 高周波ほど減衰が大きい (表皮効果)
  - **反射**: コネクタのインピーダンスミスマッチ
  - **クロストーク**: 隣接レーン間の結合 (オプション)
  - **ジッタ**: ランダムおよび確定的タイミングノイズ
- **実装**: FIRフィルタ (インパルス応答) または周波数領域モデル

### 4.2 チャネル挿入損失

ナイキスト周波数における典型的なPCIeチャネル損失：

| データレート | ナイキスト周波数 | 典型的損失   | コメント                     |
|--------------|------------------|--------------|------------------------------|
| 8 Gbps       | 4 GHz            | -15 ~ -20 dB | Gen3、中程度の損失           |
| 16 Gbps      | 8 GHz            | -25 ~ -30 dB | Gen4、大きな損失             |
| 32 Gbps      | 16 GHz           | -35 ~ -40 dB | Gen5 PAM4、非常に大きな損失  |

**等化要件**: CTLE + FFE + DFEで20-40 dBの損失を回復する必要がある。

### 4.3 チャネルインターフェース

| ポート名     | 方向   | ビット幅 | 型     | 説明                         |
|--------------|--------|----------|--------|------------------------------|
| `tx_signal`  | Input  | N/A      | `real` | アナログTx信号 (DACから)     |
| `rx_signal`  | Output | N/A      | `real` | アナログRx信号 (ADCへ)       |

---

## 5. 変調方式

### 5.1 NRZ (Non-Return-to-Zero)

- **レベル**: 2 (2値)
- **マッピング**:
  - ビット`0` → -1.0 V (またはデジタルで-127)
  - ビット`1` → +1.0 V (またはデジタルで+127)
- **シンボルレート**: ビットレートと等しい (1ビット/シンボル)
- **帯域幅**: ナイキスト周波数 = ビットレート / 2
- **使用例**: PCIe Gen3/Gen4、低速 (≤ 16 Gbps)

### 5.2 PAM4 (4-Level Pulse Amplitude Modulation)

- **レベル**: 4 (4値)
- **マッピング**:
  - ビット`00` → -0.75 V (またはデジタルで-96)
  - ビット`01` → -0.25 V (またはデジタルで-32)
  - ビット`10` → +0.25 V (またはデジタルで+32)
  - ビット`11` → +0.75 V (またはデジタルで+96)
- **シンボルレート**: ビットレートの半分 (2ビット/シンボル)
- **帯域幅**: ナイキスト周波数 = ビットレート / 4 (NRZの半分)
- **使用例**: PCIe Gen5/Gen6、高速 (≥ 32 Gbps)

**トレードオフ**: PAM4はNRZの半分の帯域幅を使用するが、より高いSNRが必要 (ノイズに敏感)。

### 5.3 変調選択の影響

| 観点                 | NRZ                          | PAM4                           |
|----------------------|------------------------------|--------------------------------|
| **帯域幅**           | 高い (ナイキスト = BR/2)     | 低い (ナイキスト = BR/4)       |
| **SNR要件**          | 低い (~16 dB、BER 1e-12用)   | 高い (~26 dB、BER 1e-12用)     |
| **等化**             | シンプル (2レベルスライサー) | 複雑 (4レベルスライサー)       |
| **DFE実装**          | 容易 (2値フィードバック)     | 困難 (多レベルフィードバック)  |
| **チャネル損失**     | 耐性が高い                   | より多くの等化が必要           |

---

## 6. モジュール階層と依存関係

### 6.1 ディレクトリ構造

```
rtl/
├── serdes_common.sv          # 共通パラメータ、型、パッケージ
├── tx/
│   ├── tx_ffe.sv             # 送信FFE (プリエンファシス)
│   ├── serializer.sv         # パラレル→シリアル変換器
│   ├── dac_model.sv          # DAC動作モデル
│   └── serdes_tx.sv          # トップレベルTx統合モジュール
├── rx/
│   ├── adc_model.sv          # ADC動作モデル
│   ├── ctle_rnm.sv           # CTLEアナログイコライザ (RNM)
│   ├── rx_ffe.sv             # 受信FFE (7タップ)
│   ├── dfe.sv                # DFE (5タップ)
│   ├── cdr.sv                # クロックデータリカバリ
│   ├── deserializer.sv       # シリアル→パラレル変換器
│   └── serdes_rx.sv          # トップレベルRx統合モジュール
├── channel/
│   └── channel_model.sv      # 伝送線路モデル (オプション)
└── modulation/
    ├── nrz_encoder.sv        # NRZシンボルマッピング
    └── pam4_encoder.sv       # PAM4シンボルマッピング

tb/
├── serdes_tx_tb.sv           # Tx単体テストベンチ
├── serdes_rx_tb.sv           # Rx単体テストベンチ
├── serdes_loopback_tb.sv     # Tx-Rx完全リンクテストベンチ
└── pcie_compliance_tb.sv     # PCIe準拠テスト
```

### 6.2 モジュールインスタンス階層

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
└── nrz_encoder / pam4_encoder (比較用)

serdes_loopback_tb
├── serdes_tx
├── channel_model
└── serdes_rx
```

### 6.3 コンパイル順序 (test_config.yaml)

完全システムテスト用：

```yaml
rtl_files:
  - serdes_common.sv          # 1. 共通定義を最初に
  - modulation/nrz_encoder.sv # 2. 変調ヘルパー
  - modulation/pam4_encoder.sv
  - tx/tx_ffe.sv              # 3. リーフモジュール
  - tx/serializer.sv
  - tx/dac_model.sv
  - rx/adc_model.sv
  - rx/ctle_rnm.sv
  - rx/rx_ffe.sv
  - rx/dfe.sv
  - rx/cdr.sv
  - rx/deserializer.sv
  - channel/channel_model.sv  # 4. チャネル (何も使用しない)
  - tx/serdes_tx.sv           # 5. Tx統合モジュール (tx/*を使用)
  - rx/serdes_rx.sv           # 6. Rx統合モジュール (rx/*を使用)
```

---

## 7. 共通定義 (serdes_common.sv)

### 7.1 パッケージ内容

```systemverilog
package serdes_pkg;

    // データレート構成
    typedef enum logic [1:0] {
        RATE_10GBPS  = 2'b00,  // 10 Gbps (PCIe Gen3)
        RATE_16GBPS  = 2'b01,  // 16 Gbps (PCIe Gen4)
        RATE_25GBPS  = 2'b10,  // 25 Gbps
        RATE_32GBPS  = 2'b11   // 32 Gbps (PCIe Gen5 PAM4)
    } data_rate_t;

    // 変調タイプ
    typedef enum logic {
        MODULATION_NRZ  = 1'b0,
        MODULATION_PAM4 = 1'b1
    } modulation_t;

    // NRZシンボルレベル (8ビット符号付き)
    parameter logic signed [7:0] NRZ_LEVEL_0 = -8'sd128;  // 論理0
    parameter logic signed [7:0] NRZ_LEVEL_1 =  8'sd127;  // 論理1

    // PAM4シンボルレベル (8ビット符号付き)
    parameter logic signed [7:0] PAM4_LEVEL_00 = -8'sd96;  // シンボル00
    parameter logic signed [7:0] PAM4_LEVEL_01 = -8'sd32;  // シンボル01
    parameter logic signed [7:0] PAM4_LEVEL_10 =  8'sd32;  // シンボル10
    parameter logic signed [7:0] PAM4_LEVEL_11 =  8'sd96;  // シンボル11

    // アナログ電圧レベル (DAC/ADCモデル用)
    parameter real ANALOG_VDD = 1.0;   // +1.0 V電源
    parameter real ANALOG_VSS = -1.0;  // -1.0 V電源

    // クロック周波数 (リファレンス用)
    parameter real CLK_100MHZ   = 100.0e6;
    parameter real CLK_312_5MHZ = 312.5e6;  // 10 Gbps用パラレルクロック
    parameter real CLK_10GHZ    = 10.0e9;   // 10 Gbps用シリアルクロック

endpackage : serdes_pkg
```

### 7.2 共通型定義

```systemverilog
// 係数構造 (FFE/DFE用)
typedef struct packed {
    logic        valid;
    logic [2:0]  addr;
    logic signed [9:0] value;
} coeff_t;

// ステータス/制御インターフェース
typedef struct packed {
    logic locked;      // CDRロックステータス
    logic error;       // エラー指示
    logic [7:0] ber;   // ビット誤り率 (監視される場合)
} status_t;
```

---

## 8. 統合上の考慮事項

### 8.1 クロックドメイン交差 (CDC)

**課題**: TxとRxは**異なるクロック**で動作 (Tx PLLとRx CDR)。

**CDC発生箇所**:
1. Txパラレルとシリアルクロック間 (serializerで処理)
2. Rxシリアルとパラレルクロック間 (deserializerで処理)
3. Rx回復クロックと外部ロジック間

**解決策**: 適切なCDC技術を使用:
- データ用のデュアルクロックFIFO
- 制御信号用の同期化回路 (2-FF)
- ドメイン交差カウンタ用のGrayコード

### 8.2 リセット戦略

**グローバルリセット**: 非同期アサート、クロックドメインごとに同期デアサート。

**リセットシーケンス**:
1. グローバル`rst_n = 0`をアサート (非同期)
2. ≥ 100 ns待機
3. 各クロックドメインに同期して`rst_n = 1`をデアサート
4. データ伝送前にPLL/CDRロックを待つ

### 8.3 較正と適応

**Tx較正**:
- チャネル特性評価に基づいてTX FFE係数をプログラム
- 通常リンクトレーニング時に1回実施 (PCIeトレーニングシーケンス)

**Rx適応**:
- **CTLE**: チャネル帯域幅に合わせて零点/極周波数を設定
- **RX FFE**: LMSまたは類似アルゴリズムを使用して係数を適応
- **DFE**: post-cursor ISIをキャンセルするためにフィードバックタップを適応
- **適応時間**: 通常約1 ms (10 Gbpsで1e6シンボル)

**適応アルゴリズム** (将来の作業、別仕様):
- `spec/adaptation_algorithms.md`を参照 (作成予定)

### 8.4 性能メトリクス

**監視すべき主要メトリクス**:
1. **BER (Bit Error Rate)**: PCIe準拠用の目標 < 1e-12
2. **Eye Height**: 垂直アイ開口 (mV)、> 100 mVであるべき
3. **Eye Width**: 水平アイ開口 (ps)、> 0.5 UIであるべき
4. **ジッタ**: トータルジッタ < 0.3 UI RMS
5. **CDRロック時間**: 通常 < 1000 UI

---

## 9. シミュレーション戦略

### 9.1 単体テスト (個別ブロック)

各モジュールを個別にテスト:
- `tx_ffe_tb.sv`, `rx_ffe_tb.sv`, `dfe_tb.sv`, `ctle_rnm_tb.sv`
- アルゴリズム正確性、係数プログラミング、飽和処理を検証

**シミュレーション時間**: テストあたり10-100 µs

### 9.2 統合テスト (Tx単体、Rx単体)

- **Tx単体**: `serdes_tx_tb.sv` → 理想的負荷へのTx信号品質を検証
- **Rx単体**: `serdes_rx_tb.sv` → ISI注入された既知パターンをRxが回復できることを検証

**シミュレーション時間**: テストあたり100-500 µs

### 9.3 システムテスト (完全リンク)

- **ループバック**: `serdes_loopback_tb.sv` → 完全Tx-Channel-Rxシミュレーション
- **BER測定**: PRBSパターンを送信、Rx出力を比較、エラーをカウント
- **アイダイアグラム**: UI境界でサンプル収集、アイをプロット

**シミュレーション時間**: 1-10 ms (統計的BER測定のため長時間)

### 9.4 準拠テスト

- **PCIe準拠**: `pcie_compliance_tb.sv` → TX/RXがPCIe仕様制限を満たすことを検証
  - Txアイマスク準拠
  - Rxジッタ耐性
  - 等化係数範囲

**シミュレーション時間**: 10-100 ms (包括的スイープ)

---

## 10. 将来の拡張

### 10.1 フェーズ1 (現在のスコープ)

✅ FFE, DFE, CTLE仕様
✅ システムアーキテクチャ定義
✅ NRZおよびPAM4変調

### 10.2 フェーズ2 (次のステップ)

- 全RTLモジュールの実装 (`tx_ffe.sv`, `rx_ffe.sv`, `dfe.sv`等)
- 単体および統合テスト用テストベンチ作成
- 仕様に対する検証

### 10.3 フェーズ3 (高度な機能)

- **適応等化アルゴリズム**: LMS, RLS, ルックアップテーブル
- **CDR実装**: Bang-bang位相検出器、PI (位相補間器)
- **PLLモデル**: 現実的なシミュレーション用のジッタ注入
- **マルチレーンサポート**: 4レーンまたは8レーンSerDes (×4, ×8 PCIe)
- **前方誤り訂正 (FEC)**: Gen5/Gen6用のRS-FEC

### 10.4 フェーズ4 (合成と検証)

- **FPGA実装**: XilinxまたはIntel FPGAプロトタイピング
- **ハードウェア検証**: 実チャネルでの測定機器を使用したテスト
- **性能最適化**: タイミングクロージャ、リソース使用量削減

---

## 11. 参考文献

### 11.1 標準規格
- **PCIe Base Specification** (v3.0/4.0/5.0/6.0): 完全なSerDes要件
- **IEEE 802.3**: Ethernet SerDes標準 (10G/25G/100G)
- **OIF-CEI-03.0**: Common Electrical I/O Implementation Agreement

### 11.2 書籍
- "High-Speed SerDes Devices and Applications" - Loi Chua
- "Jitter, Noise, and Signal Integrity at High-Speed" - Mike Peng Li

### 11.3 関連ドキュメント
- `spec/ffe_specification.md` - FFE詳細仕様
- `spec/dfe_specification.md` - DFE詳細仕様
- `spec/ctle_specification.md` - CTLE詳細仕様
- `spec/test_strategy.md` - 包括的テスト計画

---

## 12. 改訂履歴

| バージョン | 日付       | 作成者 | 説明                         |
|------------|------------|--------|------------------------------|
| 1.0        | 2025-01-11 | Claude | 初版アーキテクチャ定義       |

---

**SerDesアーキテクチャ仕様書 終わり**
