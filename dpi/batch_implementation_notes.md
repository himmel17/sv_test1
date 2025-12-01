# DPI-C Flicker Noise: バッチ方式実装ノート

## 概要

### 現在の実装（ストリーミング方式）
- **アルゴリズム**: Voss-McCartney
- **動作**: `dpi_flicker_noise()`が呼ばれるたびに、その場で乱数を生成
- **状態管理**: 10個のノイズソース（`noise_sources[10]`）を保持
- **更新パターン**: ソースiは2^iサンプルごとに更新

### 提案される変更（バッチ方式）
- **事前生成**: `init_flicker_noise()`で必要な数の乱数を全て生成
- **順次返却**: `dpi_flicker_noise()`は事前生成された乱数を1つずつ返す
- **メモリベース**: 計算からメモリアクセスへの変更

### 実現可能性
✅ **技術的に完全に可能**

---

## 実装方法

### 方法1: C内での完全事前生成

**概要**: `init_flicker_noise()`内でVoss-McCartneyアルゴリズムを使用して全サンプルを事前計算し、配列に保存する。

**実装例**:
```c
//==============================================================================
// CONFIGURATION
//==============================================================================
#define MAX_SAMPLES 10000   // 最大サンプル数（必要に応じて調整）

//==============================================================================
// STATIC STATE
//==============================================================================
static double pregenerated_noise[MAX_SAMPLES];  // 事前生成されたノイズ配列
static int current_index = 0;                   // 現在の読み出しインデックス
static int initialized = 0;                      // 初期化フラグ

//==============================================================================
// INITIALIZATION FUNCTION
//==============================================================================
static void init_flicker_noise() {
    srand(SEED);  // 固定シードで決定的生成

    // 一時的なノイズソース（Voss-McCartney用）
    double noise_sources[N_SOURCES];

    // ノイズソースの初期化
    for (int i = 0; i < N_SOURCES; i++) {
        noise_sources[i] = 2.0 * ((double)rand() / RAND_MAX) - 1.0;
    }

    // MAX_SAMPLES個のノイズサンプルを事前生成
    for (int n = 0; n < MAX_SAMPLES; n++) {
        // sample_counter = n として各ソースを更新
        for (int i = 0; i < N_SOURCES; i++) {
            if ((n & ((1UL << i) - 1)) == 0) {
                noise_sources[i] = 2.0 * ((double)rand() / RAND_MAX) - 1.0;
            }
        }

        // 全ソースの合計を計算
        double sum = 0.0;
        for (int i = 0; i < N_SOURCES; i++) {
            sum += noise_sources[i];
        }

        // スケーリングして配列に保存
        pregenerated_noise[n] = sum * (TARGET_RMS / RAW_RMS);
    }

    current_index = 0;
    initialized = 1;
}

//==============================================================================
// DPI-C EXPORTED FUNCTION
//==============================================================================
double dpi_flicker_noise(void) {
    // 初回呼び出し時に初期化
    if (!initialized) {
        init_flicker_noise();
    }

    // 境界チェック（サンプル数超過時の処理）
    if (current_index >= MAX_SAMPLES) {
        // オプション1: エラー
        // fprintf(stderr, "ERROR: Exceeded MAX_SAMPLES\n");
        // return 0.0;

        // オプション2: ループ（先頭に戻る）
        current_index = 0;
    }

    // 事前生成されたノイズを返す
    return pregenerated_noise[current_index++];
}
```

**長所**:
- DPI呼び出し時の計算コストがほぼゼロ（配列アクセスのみ）
- C内で完結（外部ファイル不要）
- Voss-McCartneyアルゴリズムを保持

**短所**:
- メモリ使用量が増加
- サンプル数の上限を事前に決める必要がある
- Python実装とは異なるRNG（C `rand()` vs Python `random`）のため、サンプル値は一致しない

---

### 方法2: Pythonデータの読み込み

**概要**: Pythonで生成したノイズデータをバイナリファイルとして保存し、C側で読み込む。

**Pythonスクリプト例** (データ生成):
```python
import numpy as np

# generate_flicker_noise.pyで生成したデータを保存
noise_samples = generate_flicker_noise(n_samples=10000)
noise_samples.astype(np.float64).tofile('flicker_noise_reference.bin')
```

**C実装例**:
```c
//==============================================================================
// CONFIGURATION
//==============================================================================
#define MAX_SAMPLES 10000
#define NOISE_DATA_FILE "flicker_noise_reference.bin"

//==============================================================================
// STATIC STATE
//==============================================================================
static double pregenerated_noise[MAX_SAMPLES];
static int current_index = 0;
static int initialized = 0;
static int num_samples_loaded = 0;

//==============================================================================
// INITIALIZATION FUNCTION
//==============================================================================
static void init_flicker_noise() {
    FILE *f = fopen(NOISE_DATA_FILE, "rb");
    if (f == NULL) {
        fprintf(stderr, "ERROR: Cannot open %s\n", NOISE_DATA_FILE);
        // フォールバック: 方法1の実装を使用
        return;
    }

    // バイナリデータを読み込み
    num_samples_loaded = fread(pregenerated_noise, sizeof(double),
                               MAX_SAMPLES, f);
    fclose(f);

    if (num_samples_loaded < MAX_SAMPLES) {
        fprintf(stderr, "WARNING: Loaded %d samples (expected %d)\n",
                num_samples_loaded, MAX_SAMPLES);
    }

    current_index = 0;
    initialized = 1;
}

//==============================================================================
// DPI-C EXPORTED FUNCTION
//==============================================================================
double dpi_flicker_noise(void) {
    if (!initialized) {
        init_flicker_noise();
    }

    if (current_index >= num_samples_loaded) {
        current_index = 0;  // ループ
    }

    return pregenerated_noise[current_index++];
}
```

**Verilator設定** (`tests/test_config.yaml`):
```yaml
- name: ideal_amp_with_noise
  verilator_extra_flags:
    - ../dpi/dpi_flicker_noise.c
  # 注意: flicker_noise_reference.binがカレントディレクトリに必要
```

**長所**:
- PythonとSystemVerilogの出力が**完全一致**
- アルゴリズムの検証が容易
- Pythonで複雑なノイズ生成も可能

**短所**:
- 外部ファイル依存
- ファイルI/Oのオーバーヘッド（初期化時のみ）
- テスト実行前にPythonスクリプトを実行する必要がある

---

## 考慮点

### 1. メモリ使用量

| 実装方式 | メモリ使用量 | 説明 |
|---------|-------------|------|
| 現在（ストリーミング） | 80 bytes | `noise_sources[10]` × 8 bytes |
| バッチ方式 (1,000サンプル) | ~7.8 KB | `1000 × 8 bytes` |
| バッチ方式 (10,000サンプル) | ~78 KB | `10000 × 8 bytes` |
| バッチ方式 (100,000サンプル) | ~781 KB | `100000 × 8 bytes` |

**推奨**: シミュレーションで必要な最大サンプル数 + 余裕（例: 1.2倍）

### 2. サンプル数の上限

**問題**: 事前にMAX_SAMPLESを決める必要がある

**解決策**:
- **オプションA - エラー**: 上限超過時にエラーメッセージを出力して`0.0`を返す
- **オプションB - ループ**: 先頭に戻る（`current_index = 0`）
- **オプションC - 動的拡張**: `realloc()`で配列を拡張（複雑）

**推奨**: シミュレーション時間から計算
```
MAX_SAMPLES = (simulation_time / clock_period) × safety_factor
例: 100us / 10ns × 1.2 = 12,000 samples
```

### 3. 性能比較

| 項目 | ストリーミング方式 | バッチ方式 |
|-----|-----------------|-----------|
| 初期化時間 | 極小 | 中〜大（全サンプル生成） |
| 呼び出しごとの計算 | 中（乱数生成+合計） | 極小（配列アクセスのみ） |
| メモリアクセス | 少（10要素） | 中（1要素/呼び出し） |
| キャッシュ効率 | 良好 | 良好（シーケンシャル） |
| 総実行時間 | O(N × M) | O(N) |

**N**: サンプル数, **M**: ノイズソース数（10）

**結論**: 長時間シミュレーションではバッチ方式が高速

### 4. Python実装との一致性

| 実装方法 | RNG | サンプル値一致 | 統計的一致 |
|---------|-----|--------------|-----------|
| 方法1（C内生成） | C `rand()` | ❌ | ✅ |
| 方法2（ファイル読込） | Python `random` | ✅ | ✅ |

**注意**: 方法1では、Pythonと異なるRNGを使用するため、サンプル値は異なるが統計的特性（RMS、スペクトル）は一致する。

### 5. リセット機能

現在の実装にはリセット機能がないため、バッチ方式でも同様に不要。

**オプション**: 明示的なリセット関数を追加する場合:
```c
void dpi_reset_flicker_noise(void) {
    current_index = 0;
    // 必要に応じて再初期化
}
```

SystemVerilog側:
```systemverilog
import "DPI-C" function void dpi_reset_flicker_noise();

initial begin
    dpi_reset_flicker_noise();  // シミュレーション開始時
end
```

---

## 結論

### 実現可能性
✅ **技術的に完全に可能** - ストリーミング方式からバッチ方式への変更は標準的なアプローチ

### 推奨される使用ケース

**バッチ方式が適している場合**:
- ✅ 長時間シミュレーション（>10,000サンプル）
- ✅ シミュレーション速度が重要
- ✅ PythonとSystemVerilogの完全一致が必要（方法2）
- ✅ サンプル数が予測可能

**ストリーミング方式が適している場合**:
- ✅ 短時間シミュレーション（<1,000サンプル）
- ✅ メモリ使用量を最小化したい
- ✅ サンプル数が予測不可能
- ✅ 無限ストリームが必要

### 実装方法の選択基準

| 要件 | 推奨方法 |
|-----|---------|
| PythonとSystemVerilogの完全一致 | **方法2** (ファイル読込) |
| 外部依存を避けたい | **方法1** (C内生成) |
| 最高速度 | **方法2** (ファイル読込) |
| 柔軟性（サンプル数変更） | **方法1** (C内生成) |

### 次のステップ

1. **要件定義**:
   - 必要な最大サンプル数を決定
   - Python一致が必要か確認
   - メモリ制約を確認

2. **実装方法の選択**:
   - 方法1 or 方法2を決定

3. **実装**:
   - `dpi_flicker_noise.c`を変更
   - 必要に応じてPythonスクリプトを更新（方法2の場合）

4. **検証**:
   - `scripts/verify_noise_match.py`で統計的検証
   - パフォーマンステスト

5. **ドキュメント更新**:
   - `dpi/README.md`と`dpi/README_ja.md`に変更内容を記載
   - `CLAUDE.md`の該当セクションを更新

---

## 参考ファイル

- **現在の実装**: `dpi/dpi_flicker_noise.c`
- **Python参照実装**: `scripts/generate_flicker_noise.py`
- **検証スクリプト**: `scripts/verify_noise_match.py`
- **テストベンチ**: `tb/ideal_amp_with_noise_tb.sv`
- **RTL**: `rtl/ideal_amp_with_noise.sv`
- **テスト設定**: `tests/test_config.yaml`

---

**作成日**: 2025-12-01
**目的**: DPI-C実装のストリーミング方式→バッチ方式変更の実現可能性と実装方法をまとめた技術ノート
