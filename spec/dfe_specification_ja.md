# DFE (Decision Feedback Equalizer) 仕様書

**ドキュメントバージョン**: 1.0
**最終更新日**: 2025-01-11
**対象**: 高速SerDes (10-25 Gbps) PCIe Gen3/4/5向け
**変調方式**: NRZ, PAM4

---

## 1. 概要

### 1.1 目的

Decision Feedback Equalizer (DFE) は、高速シリアルデータ受信機においてpost-cursor Inter-Symbol Interference (ISI, シンボル間干渉) を除去する非線形適応イコライザです。FFE (フィードフォワード) とは異なり、DFEは**過去の判定** (すでに検出されたシンボル) を使用して現在のサンプルからISIを減算し、ノイズ増幅なしに優れた等化性能を提供します。

### 1.2 主な機能

- **5タップDecision Feedback構造** (タップ数変更可能)
- **統合スライサー** (NRZ/PAM4シンボル検出用の判定回路)
- **プログラマブルフィードバック係数** による適応動作
- **8ビットデータパス** (ADCおよびFFE出力幅に対応)
- **Look-aheadアーキテクチャ** (オプション) 高速でのタイミングクロージャ用
- **PAM4対応判定ロジック** 4レベルスライシング付き
- **PCIe準拠** のフィードバック係数範囲

### 1.3 ブロック図

```
                    ┌─────────────────────────────────────────────┐
                    │         DFE (5-tap Feedback)                │
                    │                                             │
data_in [7:0] ──>───┤►─(+)────────►[SLICER]────►[Delay]──►──────►├──> data_out [7:0]
(from FFE/CTLE)     │   ▲              │           │              │    (detected symbols)
                    │   │              │     ┌─────┴────┐         │
                    │   │              └────►│  D1─D2─  │         │
                    │   │                    │  D3─D4─  │         │
                    │   │                    │    D5    │         │
                    │   │                    └────┬─────┘         │
                    │   │                         │               │
                    │   │  ┌──────────────────────┘               │
                    │   │  │   ┌───┬───┬───┬───┬───┐             │
                    │   └──┤─  │×C1│×C2│×C3│×C4│×C5│             │
                    │      │   └───┴───┴───┴───┴───┘             │
                    │      └────────►[Σ Feedback]                │
                    │                                             │
coeff_in ───────────┤►─ Coefficient Update Interface             │
                    │   (coeff_wr_en, coeff_addr, coeff_data)    │
                    └─────────────────────────────────────────────┘
     clk ──>────┐
    rst_n ──>───┘
```

**FFEとの主な違い**: DFEフィードバックは生サンプルではなく**検出シンボル** (硬判定) を使用。

---

## 2. インターフェース仕様

### 2.1 ポート定義

| ポート名         | 方向   | ビット幅       | 型             | 説明                                             |
|------------------|--------|----------------|----------------|--------------------------------------------------|
| `clk`            | Input  | 1              | `logic`        | システムクロック (パラレルデータレートクロック)  |
| `rst_n`          | Input  | 1              | `logic`        | Active-low同期リセット                           |
| `data_in`        | Input  | `DATA_WIDTH`   | `logic signed` | 入力サンプル (FFE/CTLE出力、8ビット)             |
| `data_out`       | Output | `DATA_WIDTH`   | `logic signed` | 検出シンボル (判定出力)                          |
| `decision_valid` | Output | 1              | `logic`        | 判定出力有効フラグ                               |
| `coeff_wr_en`    | Input  | 1              | `logic`        | 係数書き込みイネーブル                           |
| `coeff_addr`     | Input  | `ADDR_WIDTH`   | `logic`        | 係数アドレス (タップ1-5)                         |
| `coeff_data`     | Input  | `COEFF_WIDTH`  | `logic signed` | フィードバック係数値 (符号付き)                  |
| `coeff_updated`  | Output | 1              | `logic`        | 係数更新完了パルス                               |
| `threshold`      | Input  | `THRESH_WIDTH` | `logic signed` | スライサー閾値 PAM4用 (3閾値必要)                |
| `modulation`     | Input  | 1              | `logic`        | 0 = NRZ (2レベル), 1 = PAM4 (4レベル)            |

**注記:**
- `data_in`: FFE/CTLEからの等化済みだがノイズを含むサンプル
- `data_out`: クリーンな検出シンボル (NRZ/PAM4レベルに量子化)
- `decision_valid`: 初期タップ充填後 (5サイクル後) にアサート
- PAM4は4レベルを区別するために3つの閾値が必要

### 2.2 パラメータ定義

| パラメータ     | デフォルト | 範囲       | 説明                                               |
|----------------|------------|------------|----------------------------------------------------|
| `TAP_COUNT`    | 5          | 1-7        | フィードバックタップ数                             |
| `DATA_WIDTH`   | 8          | 6-12       | データパス幅 (サンプル/シンボルあたりのビット数)   |
| `COEFF_WIDTH`  | 10         | 8-16       | 係数ビット幅 (精度を決定)                          |
| `ADDR_WIDTH`   | 3          | 1-4        | 係数アドレスビット幅                               |
| `THRESH_WIDTH` | 8          | 6-10       | スライサー閾値ビット幅 (閾値あたり)                |
| `ACCUM_WIDTH`  | 18         | 16-24      | フィードバックアキュムレータビット幅               |
| `LOOKAHEAD`    | 0          | 0-1        | Look-aheadアーキテクチャ有効化 (0=無効, 1=有効)    |

**パラメータ選択ガイドライン:**
- `COEFF_WIDTH ≥ DATA_WIDTH` 十分な精度のため
- `ACCUM_WIDTH ≥ DATA_WIDTH + COEFF_WIDTH + log2(TAP_COUNT)`
- `LOOKAHEAD = 1` >10 Gbps動作時に推奨 (フィードバックタイミングを解決)

---

## 3. 機能説明

### 3.1 DFEアルゴリズム

DFEは現在の判定を行う前に過去のシンボルからISIを減算します：

```
decision[n] = SLICER( data_in[n] - Σ(i=1 to N) C[i] × decision[n-i] )
```

ここで：
- `decision[n]`: 時刻nにおける検出シンボル
- `data_in[n]`: 入力サンプル (ノイズあり、ISIあり)
- `C[i]`: タップiのフィードバック係数
- `decision[n-i]`: 以前に検出されたシンボル (iシンボル前)
- `SLICER()`: 判定関数 (閾値比較)

**重要な洞察**: フィードバックはソフト値ではなく**硬判定** (量子化シンボル) を使用。

### 3.2 フィードバックパス

#### 3.2.1 フィードバック計算 (組み合わせ回路)

```systemverilog
// フィードバック計算の疑似コード
feedback_sum = 0;
for (i = 1; i <= TAP_COUNT; i++) {
    feedback_sum += coefficient[i] * decision_history[i];
}
compensated_input = data_in - feedback_sum;
```

**タイミングクリティカル**: 非look-aheadアーキテクチャでは1クロックサイクル内に完了する必要がある。

#### 3.2.2 判定履歴 (シフトレジスタ)

```systemverilog
// 過去TAP_COUNT個の判定を保存
logic signed [DATA_WIDTH-1:0] decision_history [1:TAP_COUNT];

always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 1; i <= TAP_COUNT; i++) begin
            decision_history[i] <= '0;
        end
    end else begin
        decision_history[1] <= data_out;  // 最新の判定
        for (int i = 2; i <= TAP_COUNT; i++) begin
            decision_history[i] <= decision_history[i-1];
        end
    end
end
```

### 3.3 スライサー (判定回路)

スライサーは補償済み入力を最も近いシンボルレベルに量子化します。

#### 3.3.1 NRZスライサー (2レベル)

NRZ用 (modulation = 0):

```
シンボルレベル: -127 (論理0), +127 (論理1)
閾値: 0

if (compensated_input > threshold) then
    decision = +127  (論理1)
else
    decision = -127  (論理0)
```

#### 3.3.2 PAM4スライサー (4レベル)

PAM4用 (modulation = 1):

```
シンボルレベル: -96 (00), -32 (01), +32 (10), +96 (11)
閾値: T1 = -64, T2 = 0, T3 = +64

if (compensated_input > T3)         decision = +96  (11)
else if (compensated_input > T2)    decision = +32  (10)
else if (compensated_input > T1)    decision = -32  (01)
else                                decision = -96  (00)
```

**実装**: 効率的なマルチレベルスライシングのためコンパレータ + プライオリティエンコーダを使用。

### 3.4 Look-Aheadアーキテクチャ (オプション)

**問題**: 高速 (>10 Gbps) では、フィードバックパスのタイミングが1クロックサイクル内に閉じない可能性がある。

**解決策**: 投機的計算 - **複数の可能な判定**を並列計算し、正しいものを選択。

#### 3.4.1 Look-Ahead原理

1タップlook-ahead DFEの場合：

```
// 次の判定の2つの可能性を事前計算
if (current_decision == -127) {
    next_feedback = C[1] × (-127)
} else {  // current_decision == +127
    next_feedback = C[1] × (+127)
}

// 両方のケースの補償済み入力を計算
compensated_if_low  = data_in - next_feedback_for_low
compensated_if_high = data_in - next_feedback_for_high

// 実際の現在の判定に基づいて正しいものを選択
compensated_input = (current_decision == -127) ? compensated_if_low : compensated_if_high
```

**トレードオフ**: 最初のタップのロジックが2倍になるが、より高いクロック周波数が可能。

---

## 4. タイミング要件

### 4.1 クリティカルタイミングパス

**パス**: `data_in` → フィードバック減算 → スライサー → `data_out` → フィードバックシフトレジスタ → 係数乗算 → 合計 → 減算へ戻る

**タイミングバジェット** (例: 312.5 MHzパラレルクロック):
- クロック周期: 3.2 ns
- セットアップ/ホールド: 0.5 ns
- **ロジックに利用可能**: 2.7 ns
- フィードバックMultiply-Accumulate (MAC): ~1.5 ns
- 減算 + スライサーコンパレータ: ~1.0 ns
- ルーティング: ~0.2 ns
- **合計**: ~2.7 ns ✓ (タイミングを満たす)

**>10 Gbpsの場合**: Look-aheadまたはパイプライン化が必要な可能性がある。

### 4.2 レイテンシ

- **判定レイテンシ**: 1クロックサイクル (data_inからdata_outまで)
- **適応レイテンシ**: 1クロックサイクル (係数更新から効果まで)
- **初期タップ充填**: 5サイクル (`decision_valid`がアサートされるまで)

### 4.3 タイミング図

```
Clock      : ─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─
             : └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘
rst_n      : ─────────┐─────────────────────
             :        └──────────────────>
data_in    : ──<D0><D1><D2><D3><D4><D5><D6>─
             :     │   │   │   │   │
decision   : ──────┴───<S1><S2><S3><S4><S5>─
             :              ▲       ▲
             :              └───┬───┘
             :              フィードバックパス
decision_valid:─────────────────┐───────────
             :                  └──────────>
```

**注記**: 最初の5サイクルは初期化 (判定履歴の充填)。

---

## 5. 係数管理

### 5.1 係数表現

FFEと同じ: **符号付き固定小数点**形式 (10ビットでS.IIIIIIII.F)。

### 5.2 デフォルト係数値 (リセット状態)

5タップDFE、全係数を0に初期化 (フィードバックなし)：

| タップインデックス | タップ名        | デフォルト値 (10ビット) | 16進数  |
|--------------------|-----------------|-------------------------|---------|
| 1                  | Post-cursor 1   | 0                       | 0x000   |
| 2                  | Post-cursor 2   | 0                       | 0x000   |
| 3                  | Post-cursor 3   | 0                       | 0x000   |
| 4                  | Post-cursor 4   | 0                       | 0x000   |
| 5                  | Post-cursor 5   | 0                       | 0x000   |

**根拠**: 起動時はDFE無効 (バイパスモード)。

### 5.3 典型的なDFE係数値

PCIe準拠受信機DFE用 (NRZ):

| タップインデックス | 典型的値       | 範囲          | 注記                                 |
|--------------------|----------------|---------------|--------------------------------------|
| 1                  | -0.15 ～ -0.25 | -0.3 ～ 0.0   | 最初のpost-cursor (最大ISI)          |
| 2                  | -0.05 ～ -0.15 | -0.2 ～ 0.0   | 2番目のpost-cursor                   |
| 3                  | -0.02 ～ -0.08 | -0.15 ～ 0.0  | 3番目のpost-cursor                   |
| 4                  | -0.01 ～ -0.05 | -0.1 ～ 0.0   | 4番目のpost-cursor (減衰するISI)     |
| 5                  | 0.0 ～ -0.03   | -0.08 ～ 0.0  | 5番目のpost-cursor (最小ISI)         |

**符号規約**: 負の係数はpost-cursor ISI成分を**減算**する。

---

## 6. 適応アルゴリズム (プレースホルダー)

### 6.1 概要

DFE係数はチャネル変動を追跡するために**適応**する必要があります。一般的なアルゴリズム：

1. **Least Mean Squares (LMS)**: 勾配降下最小化
2. **Sign-Sign LMS**: 符号ビットのみを使用した簡略化LMS
3. **Look-Up Table (LUT)**: 既知のチャネル用の事前計算係数

### 6.2 LMS適応 (概念的)

```
error[n] = data_in[n] - decision[n]  // エラー信号

for (i = 1 to TAP_COUNT) {
    C[i] = C[i] - μ × error[n] × decision[n-i]
}
```

ここで`μ`はステップサイズ (学習率)。

**実装ノート**: 適応ロジックは**別モジュール** (コアDFEの一部ではない)。`spec/dfe_adaptation.md`を参照 (将来のドキュメント)。

### 6.3 手動係数プログラミング

テストと立ち上げのため、係数は係数インターフェースを介して**手動プログラム**可能 (FFEと同じ)。

---

## 7. テスト計画

### 7.1 単体テスト: バイパスモード (フィードバックなし)

**目的**: 全係数 = 0でのスライサー動作を検証。

**手順**:
1. 全DFE係数を0に設定
2. modulation = 0 (NRZ), threshold = 0に設定
3. 交互レベルを印加: data_in = +100, -100, +100, -100
4. **期待結果**: data_out = +127, -127, +127, -127 (スライサーが正しく量子化)

**合格基準**: 出力が期待シンボルレベルと完全一致。

### 7.2 単体テスト: 単一タップフィードバック (NRZ)

**目的**: 1タップでのフィードバック計算を検証。

**手順**:
1. C[1] = -128 (約-0.25)に設定、その他は全て0
2. modulation = 0 (NRZ), threshold = 0に設定
3. テストシーケンスを印加: data_in = +50, +50, +50 (定数)
4. **期待結果**:
   - サイクル1: decision = +127 (事前のフィードバックなし)
   - サイクル2: feedback = -128 × (+127) ≈ -32, compensated = +50 - (-32) = +82 → decision = +127
   - サイクル3+: サイクル2と同じ (定常状態)

**合格基準**: フィードバックがスライシング前に入力を正しく変更。

### 7.3 単体テスト: マルチタップフィードバック

**目的**: 全5タップが正しく動作することを検証。

**手順**:
1. 係数設定: C[1] = -128, C[2] = -64, C[3] = -32, C[4] = -16, C[5] = -8
2. ステップ入力を印加: data_in = 0 → +100 (ステップ遷移)
3. decision_historyシフトレジスタの進行を監視
4. **期待結果**: 各タップが総フィードバックに比例して寄与

**合格基準**: feedback sum = Σ(C[i] × decision[i]) が±1 LSB以内。

### 7.4 単体テスト: PAM4スライサー

**目的**: PAM4の4レベルスライシングを検証。

**手順**:
1. modulation = 1 (PAM4)に設定
2. 閾値設定: T1 = -64, T2 = 0, T3 = +64
3. テストレベルを印加: data_in = -80, -40, +40, +80
4. **期待結果**: data_out = -96, -32, +32, +96 (正しいレベルマッピング)

**合格基準**: 全4 PAM4レベルが正しく検出される。

### 7.5 統合テスト: ISIキャンセル (NRZ)

**目的**: DFEが現実的なシナリオでpost-cursor ISIを除去することを検証。

**手順**:
1. ISIを持つチャネルを生成: post-cursorテール = メインパルスの20%を印加
2. DFE構成: C[1] = -102 (約-0.2)
3. PRBS7 NRZパターンを印加
4. 出力で**BER (Bit Error Rate)** を測定

**合格基準**:
- DFEなしのBER: >1e-4 (ISIによる高いエラー率)
- DFEありのBER: <1e-9 (クリーンなアイ、ISIキャンセル)

### 7.6 統合テスト: 動作中の係数更新

**目的**: 動的係数プログラミングを検証。

**手順**:
1. DFEをデフォルト係数 (全0) で開始
2. テストパターンで100サイクル実行
3. coeff_wr_enインターフェース経由でC[1]を-128に更新
4. `coeff_updated`パルスを確認
5. 100サイクル継続、動作変化を確認

**合格基準**:
- 係数更新が1サイクルで完了
- 出力動作が新しい係数を即座に反映

### 7.7 ストレステスト: 最大フィードバック

**目的**: 極端なケースでの飽和保護を検証。

**手順**:
1. 全係数を最大負値に設定: C[i] = -512 (10ビット)
2. 最悪ケース入力を印加: 全ての以前の判定 = +127
3. フィードバック合計と補償済み入力をオーバーフローについて確認

**合格基準**:
- 算術オーバーフローまたはX状態なし
- 補償済み入力が正しく飽和

---

## 8. SystemVerilog実装ノート

### 8.1 モジュール宣言テンプレート

```systemverilog
`timescale 1ns / 1ps

// Decision Feedback Equalizer (DFE) - 5タップフィードバック
// Verilatorシミュレーション検証用のDesign Under Test (DUT)

module dfe #(
    parameter int TAP_COUNT    = 5,
    parameter int DATA_WIDTH   = 8,
    parameter int COEFF_WIDTH  = 10,
    parameter int ADDR_WIDTH   = 3,
    parameter int THRESH_WIDTH = 8,
    parameter int ACCUM_WIDTH  = 18,
    parameter int LOOKAHEAD    = 0
)(
    input  logic                           clk,              // システムクロック
    input  logic                           rst_n,            // Active-lowリセット
    input  logic signed [DATA_WIDTH-1:0]   data_in,          // 入力サンプル
    output logic signed [DATA_WIDTH-1:0]   data_out,         // 検出シンボル
    output logic                           decision_valid,   // 出力有効
    input  logic                           coeff_wr_en,      // 係数書き込み
    input  logic [ADDR_WIDTH-1:0]          coeff_addr,       // 係数アドレス
    input  logic signed [COEFF_WIDTH-1:0]  coeff_data,       // 係数データ
    output logic                           coeff_updated,    // 更新完了
    input  logic signed [THRESH_WIDTH-1:0] threshold[0:2],   // PAM4閾値 (3つ)
    input  logic                           modulation        // 0=NRZ, 1=PAM4
);

    // 内部信号
    logic signed [DATA_WIDTH-1:0]  decision_history [1:TAP_COUNT];
    logic signed [COEFF_WIDTH-1:0] coeff [1:TAP_COUNT];
    logic signed [ACCUM_WIDTH-1:0] feedback_sum;
    logic signed [DATA_WIDTH-1:0]  compensated_input;
    logic signed [DATA_WIDTH-1:0]  decision;
    int cycle_count;

    // ... 実装 ...

endmodule
```

### 8.2 主要実装ガイドライン

#### 8.2.1 フィードバック計算 (組み合わせ回路 - クリティカルパス)

```systemverilog
always_comb begin
    feedback_sum = '0;
    for (int i = 1; i <= TAP_COUNT; i++) begin
        feedback_sum += decision_history[i] * coeff[i];
    end
end

// 補償済み入力 (入力からフィードバックを減算)
always_comb begin
    logic signed [ACCUM_WIDTH-1:0] temp;
    temp = data_in - (feedback_sum >>> (COEFF_WIDTH - 1));

    // DATA_WIDTHへの飽和
    if (temp > $signed((2**(DATA_WIDTH-1))-1)) begin
        compensated_input = (2**(DATA_WIDTH-1)) - 1;
    end else if (temp < $signed(-(2**(DATA_WIDTH-1)))) begin
        compensated_input = -(2**(DATA_WIDTH-1));
    end else begin
        compensated_input = temp[DATA_WIDTH-1:0];
    end
end
```

#### 8.2.2 スライサー (組み合わせ回路)

```systemverilog
always_comb begin
    if (modulation == 1'b0) begin
        // NRZスライサー (2レベル)
        if (compensated_input > threshold[1]) begin
            decision = $signed(8'd127);  // 論理1
        end else begin
            decision = $signed(-8'd128); // 論理0
        end
    end else begin
        // PAM4スライサー (4レベル)
        if (compensated_input > threshold[2]) begin
            decision = $signed(8'd96);   // シンボル11
        end else if (compensated_input > threshold[1]) begin
            decision = $signed(8'd32);   // シンボル10
        end else if (compensated_input > threshold[0]) begin
            decision = $signed(-8'd32);  // シンボル01
        end else begin
            decision = $signed(-8'd96);  // シンボル00
        end
    end
end
```

#### 8.2.3 判定履歴更新 (順序回路)

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 1; i <= TAP_COUNT; i++) begin
            decision_history[i] <= '0;
        end
        data_out <= '0;
        cycle_count <= 0;
        decision_valid <= 1'b0;
    end else begin
        // 判定出力をレジスタ
        data_out <= decision;

        // 判定履歴をシフト
        decision_history[1] <= decision;
        for (int i = 2; i <= TAP_COUNT; i++) begin
            decision_history[i] <= decision_history[i-1];
        end

        // TAP_COUNTサイクル後に判定有効
        if (cycle_count < TAP_COUNT) begin
            cycle_count <= cycle_count + 1;
            decision_valid <= 1'b0;
        end else begin
            decision_valid <= 1'b1;
        end
    end
end
```

#### 8.2.4 係数管理 (順序回路)

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        for (int i = 1; i <= TAP_COUNT; i++) begin
            coeff[i] <= '0;  // 0に初期化 (DFE無効)
        end
        coeff_updated <= 1'b0;
    end else begin
        coeff_updated <= 1'b0;
        if (coeff_wr_en && coeff_addr > 0 && coeff_addr <= TAP_COUNT) begin
            coeff[coeff_addr] <= coeff_data;
            coeff_updated <= 1'b1;
        end
    end
end
```

### 8.3 Look-Ahead実装 (高度 - オプション)

```systemverilog
generate
    if (LOOKAHEAD == 1) begin : gen_lookahead
        // 最初のタップの投機的計算
        logic signed [DATA_WIDTH-1:0] feedback_if_prev_low;
        logic signed [DATA_WIDTH-1:0] feedback_if_prev_high;

        always_comb begin
            // 両方の可能性のフィードバックを事前計算
            feedback_if_prev_low  = coeff[1] * $signed(-8'd128);  // prev = -128の場合
            feedback_if_prev_high = coeff[1] * $signed(8'd127);   // prev = +127の場合

            // 実際の以前の判定に基づいて選択
            // (これによりクリティカルパスが切断される)
        end
        // ... (実装詳細は簡潔化のため省略) ...
    end
endgenerate
```

### 8.4 合成考慮事項

- **クリティカルパス最適化**:
  - タイミングが閉じない場合、フィードバックMACをパイプライン化 (1サイクルレイテンシ追加)
  - >10 Gbpsで最初のタップにlook-aheadを使用
  - フィードバックロジックをスライサーの近くにフロアプラン配置
- **リソース使用量**:
  - 乗算器: TAP_COUNT × DSPブロック
  - コンパレータ: 1 (NRZ) または3 (PAM4)
- **メタスタビリティ**: 該当なし (完全同期設計)

### 8.5 検証フック

```systemverilog
`ifdef SIMULATION
    // 波形解析用のデバッグ信号
    logic signed [ACCUM_WIDTH-1:0] debug_feedback_sum;
    logic signed [DATA_WIDTH-1:0]  debug_compensated;
    logic signed [DATA_WIDTH-1:0]  debug_decision;

    assign debug_feedback_sum = feedback_sum;
    assign debug_compensated  = compensated_input;
    assign debug_decision     = decision;
`endif
```

---

## 9. テストベンチ要件

### 9.1 テストベンチモジュールテンプレート

```systemverilog
`timescale 1ns / 1ps

module dfe_tb #(
    parameter SIM_TIMEOUT = 200000  // 200 µs (BERテスト用により長く)
);

    // クロック生成
    logic clk = 0;
    always #1.6 clk = ~clk;  // 312.5 MHz

    // DUT信号
    logic       rst_n;
    logic signed [7:0]  data_in;
    logic signed [7:0]  data_out;
    logic       decision_valid;
    logic       coeff_wr_en;
    logic [2:0] coeff_addr;
    logic signed [9:0]  coeff_data;
    logic       coeff_updated;
    logic signed [7:0]  threshold [0:2];
    logic       modulation;

    // DUTインスタンス化
    dfe #(
        .TAP_COUNT(5),
        .DATA_WIDTH(8),
        .COEFF_WIDTH(10)
    ) dut (.*);

    // VCDダンプ
    initial begin
        $dumpfile("sim/waves/dfe.vcd");
        $dumpvars(0, dfe_tb);
    end

    // ヘルパータスク: 係数プログラム
    task program_coeff(input int addr, input int value);
        begin
            @(posedge clk);
            coeff_wr_en = 1'b1;
            coeff_addr = addr;
            coeff_data = value;
            @(posedge clk);
            coeff_wr_en = 1'b0;
            @(posedge clk);  // coeff_updatedパルスを待つ
        end
    endtask

    // テストシーケンス
    int error_count = 0;
    initial begin
        // (テスト手順についてはセクション7を参照)

        if (error_count == 0) begin
            $display("*** PASSED: All DFE tests passed successfully ***");
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

### 9.2 テスト構成 (test_config.yaml)

```yaml
- name: dfe
  enabled: true
  description: "DFE 5タップDecision Feedback Equalizerテスト"
  top_module: dfe_tb
  testbench_file: dfe_tb.sv
  rtl_files:
    - dfe.sv
  verilator_extra_flags:
    - --trace-underscore
  sim_timeout: "200us"  # BER測定用により長く
```

---

## 10. 参考文献

### 10.1 標準規格
- **PCIe Base Specification** (v3.0/4.0/5.0): 受信機等化要件
- **OIF-CEI-03.0**: Common Electrical I/O Implementation Agreement

### 10.2 論文
- J. Winters, R. Gitlin, "Electrical Signal Processing Techniques in Long-Haul Fiber-Optic Systems"
- J. Cioffi, "A Multicarrier Primer" (DFE基礎)

### 10.3 関連ドキュメント
- `spec/ffe_specification.md` - Feed-Forward Equalizer
- `spec/ctle_specification.md` - Continuous-Time Linear Equalizer
- `spec/serdes_architecture.md` - システムレベルSerDesアーキテクチャ

---

## 11. 改訂履歴

| バージョン | 日付       | 作成者 | 説明                     |
|------------|------------|--------|--------------------------|
| 1.0        | 2025-01-11 | Claude | 初版仕様書作成           |

---

## 付録A: DFE vs. FFE比較

| 観点                 | FFE (Feed-Forward)                 | DFE (Decision Feedback)           |
|----------------------|------------------------------------|-----------------------------------|
| **入力**             | 生のノイズを含むサンプル           | 等化済みサンプル (FFE/CTLE後)     |
| **フィードバック**   | なし (純粋にフィードフォワード)    | 過去の検出シンボル                |
| **ノイズ**           | 高周波ノイズを増幅                 | ノイズ増幅なし                    |
| **ISI**              | Pre/post-cursor ISIをキャンセル    | Post-cursor ISIのみ               |
| **線形性**           | 線形フィルタ (FIR)                 | 非線形 (硬判定を使用)             |
| **タイミング**       | タイミングを満たしやすい           | クリティカルなフィードバックパス  |
| **性能**             | 軽度のISIに良好                    | 重度のISIにより良好               |
| **典型的配置**       | Tx (プリエンファシス) または初期Rx | 後期Rx (FFE/CTLE後)               |

**ベストプラクティス**: 最適な等化のために**FFE + DFEをカスケード**使用 (FFEがpre-cursorを除去、DFEがpost-cursorを除去)。

---

**DFE仕様書 終わり**
