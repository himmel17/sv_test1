# run_test.py 使用ガイド

SystemVerilog テストベンチランナーの完全解説

## 目次

1. [概要](#概要)
2. [基本的な使い方](#基本的な使い方)
3. [アーキテクチャ](#アーキテクチャ)
4. [主要なクラスと機能](#主要なクラスと機能)
5. [タイムアウト設定](#タイムアウト設定)
6. [**NEW** タイムスケール対応](#タイムスケール対応)
7. [コマンドライン引数](#コマンドライン引数)
8. [テストフロー](#テストフロー)
9. [トラブルシューティング](#トラブルシューティング)

---

## 1. 概要

`run_test.py` は、SystemVerilog テストベンチを Verilator でコンパイル・実行し、GTKWave で波形を表示するための Python スクリプトです。

### 1.1. 主な特徴

- **YAML ベース設定**: `tests/test_config.yaml` で複数のテストを管理
- **自動化されたフロー**: コンパイル → シミュレーション → 波形生成を一括実行
- **柔軟なタイムアウト制御**: シミュレーション時間と実行時間の両方を設定可能
- **サブディレクトリ対応**: RTL ファイルとテストベンチを階層的に管理

### 1.2. 依存関係

```python
import os
import sys
import subprocess
import argparse
from pathlib import Path
import shutil

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip3 install pyyaml")
    sys.exit(1)
```

PyYAML ライブラリが必須です。インストールされていない場合はエラーメッセージを表示して終了します。

---

## 2. 基本的な使い方

### 2.1. 全テストのリスト表示

```bash
python3 scripts/run_test.py --list
```

出力例：
```
Available tests:
------------------------------------------------------------
  ✓ counter              - 8-bit counter test
  ✓ demux_4bit           - 4-bit demultiplexer test
```

### 2.2. 特定のテストを実行

```bash
python3 scripts/run_test.py --test counter
```

### 2.3. すべての有効なテストを実行

```bash
python3 scripts/run_test.py --all
```

### 2.4. 波形ビューアを起動

```bash
python3 scripts/run_test.py --test counter --view
```

### 2.5. クリーンビルド

```bash
python3 scripts/run_test.py --clean --test counter
```

---

## 3. アーキテクチャ

スクリプトは以下の 3 つの主要コンポーネントで構成されています：

```
┌─────────────────────────────────────────┐
│  tests/test_config.yaml                 │
│  (テスト定義とパラメータ)                │
└───────────────┬─────────────────────────┘
                │
                v
┌─────────────────────────────────────────┐
│  TestConfig クラス                       │
│  - YAML の読み込みと解析                 │
│  - 有効なテストのフィルタリング           │
└───────────────┬─────────────────────────┘
                │
                v
┌─────────────────────────────────────────┐
│  TestRunner クラス                       │
│  - Verilator コンパイル                  │
│  - シミュレーション実行                  │
│  - GTKWave 起動                         │
└─────────────────────────────────────────┘
```

---

## 4. 主要なクラスと機能

### 4.1. TestConfig クラス

YAML 設定ファイルを管理するクラスです。

```python
class TestConfig:
    """Manages test configuration from YAML file"""

    def __init__(self, config_file):
        self.config_file = Path(config_file)
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(self.config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.project = self.config.get('project', {})
        self.verilator = self.config.get('verilator', {})
        self.tests = self.config.get('tests', [])
```

**主なメソッド**:

- `get_enabled_tests()`: 有効なテストのみを返す
- `get_test(test_name)`: 特定のテストの設定を取得
- `list_tests()`: すべてのテスト名を返す

### 4.2. pathlib.Path によるパス操作

このスクリプトでは、パス操作に Python 3.4+ で導入された `pathlib.Path` クラスを使用しています。

#### 4.2.1. `/` 演算子によるパス結合

`pathlib.Path` は **`/` 演算子でパスを結合できる**という特徴があります。これは `__truediv__` メソッドの演算子オーバーロードによって実現されています。

**従来の方法（文字列連結）との比較**:

```python
# ❌ 文字列連結（非推奨）
path = "/home/user" + "/" + "tests" + "/" + "config.yaml"  # 冗長、OS依存の問題

# ❌ os.path.join（古いスタイル）
import os
path = os.path.join("/home/user", "tests", "config.yaml")  # 文字列を返す

# ✅ pathlib（現代的・推奨）
from pathlib import Path
path = Path("/home/user") / "tests" / "config.yaml"  # Pathオブジェクトを返す
```

#### 4.2.2. 実際のコード例

このスクリプトでは、以下のように `/` 演算子が使用されています：

```python
# main() 関数内（407-411行目）
project_root = Path(__file__).parent.parent  # Pathオブジェクト
args.config = "tests/test_config.yaml"        # 文字列

# / 演算子でパス結合
config = TestConfig(project_root / args.config)
# 結果: Path("/home/.../sv_test1/tests/test_config.yaml")
```

実行例：
```python
# スクリプトが /home/rs133057/src/github.com/himmel17/sv_test1/scripts/run_test.py にある場合

project_root = Path(__file__).parent.parent
# 結果: Path("/home/rs133057/src/github.com/himmel17/sv_test1")

config_path = project_root / "tests/test_config.yaml"
# 結果: Path("/home/rs133057/src/github.com/himmel17/sv_test1/tests/test_config.yaml")
```

#### 4.2.3. `/` 演算子のメリット

1. **OS非依存**: Windows（`\`）と Linux/macOS（`/`）の違いを自動処理
   ```python
   # Windows でも Linux でも同じコードで動作
   path = Path("C:/Users") / "docs" / "file.txt"  # Windows
   path = Path("/home") / "user" / "file.txt"     # Linux
   ```

2. **可読性**: 直感的でわかりやすいパス構築
   ```python
   # 一目でパス構造がわかる
   rtl_dir = project_root / "rtl"
   counter_sv = rtl_dir / "counter.sv"
   ```

3. **型安全**: `Path` オブジェクトとして扱えるため、文字列連結ミスを防げる
   ```python
   path = Path("/home") / "user"
   print(type(path))  # <class 'pathlib.PosixPath'>

   # Path オブジェクトの便利なメソッドが使える
   path.exists()      # ファイル存在確認
   path.is_file()     # ファイルかどうか
   path.parent        # 親ディレクトリ
   path.name          # ファイル名
   ```

4. **豊富なメソッド**: パス操作用の便利なメソッドが多数用意されている
   ```python
   path = Path("/home/user/docs/file.txt")
   path.parent       # Path("/home/user/docs")
   path.name         # "file.txt"
   path.stem         # "file"
   path.suffix       # ".txt"
   path.parts        # ('/', 'home', 'user', 'docs', 'file.txt')
   ```

#### 4.2.4. 内部の仕組み

`Path` クラスは以下のように `__truediv__` を実装しています：

```python
class Path:
    def __truediv__(self, other):
        # other（文字列やPathオブジェクト）を結合して新しいPathを返す
        return self.__class__(self._raw_path, other)
```

このため、`project_root / args.config` は実際には `project_root.__truediv__(args.config)` というメソッド呼び出しと同じです。

### 4.3. TestRunner クラス

個々のテストを実行するクラスです。

```python
class TestRunner:
    """Runs individual test cases"""

    def __init__(self, project_root, project_config, verilator_config, test_config):
        self.project_root = Path(project_root)
        self.project_config = project_config
        self.verilator_config = verilator_config
        self.test_config = test_config

        # Setup paths
        self.rtl_dir = self.project_root / project_config.get('rtl_dir', 'rtl')
        self.tb_dir = self.project_root / project_config.get('tb_dir', 'tb')
        self.sim_dir = self.project_root / project_config.get('sim_dir', 'sim')
        self.obj_dir = self.project_root / project_config.get('obj_dir', 'sim/obj_dir')
        self.waves_dir = self.project_root / project_config.get('waves_dir', 'sim/waves')
```

**主なメソッド**:

- `clean()`: シミュレーション成果物をクリーンアップ
- `verilate()`: Verilator でコンパイル
- `run_simulation()`: シミュレーション実行
- `view_waveform()`: GTKWave 起動
- `run()`: 完全なテストフローを実行
- **⭐ NEW** `get_effective_timescale()`: テストの有効なタイムスケールを取得（自動検出 + YAML オーバーライド）
- **⭐ NEW** `validate_timescales()`: タイムスケールの整合性を検証し、混在を警告

### 4.4. タイムスケール関連の新機能

#### 4.4.1. extract_timescale() 関数

SystemVerilog ファイルから `timescale` ディレクティブを抽出します。

```python
def extract_timescale(sv_file_path):
    """
    SystemVerilog ファイルから timescale ディレクティブを解析

    Args:
        sv_file_path: SystemVerilog ファイルのパス

    Returns:
        tuple: (unit, precision) 例: ('1ns', '1ps'), ('1ps', '1fs')
               timescale が見つからない場合は (None, None)
    """
    # ファイルを開いて timescale 行を検索
    # 正規表現で解析: `timescale 1ns / 1ps
    # 係数付きタイムスケールにも対応: `timescale 100fs / 1fs
```

**使用例**:
```python
timescale = extract_timescale("tb/counter_tb.sv")
# 結果: ('1ns', '1ps')
```

#### 4.4.2. TestRunner.get_effective_timescale() メソッド

テストの有効なタイムスケールを決定します（ハイブリッドアプローチ）。

```python
def get_effective_timescale(self):
    """
    このテストの有効なタイムスケールを決定

    戦略（ハイブリッドアプローチ）:
    1. YAML 設定で 'timescale' が明示的に設定されている場合、それを使用（オーバーライド）
    2. それ以外の場合、テストベンチファイルから自動検出
    3. フォールバック: RTL ファイルをチェック
    4. 最終フォールバック: デフォルトの ('1ns', '1ps')

    Returns:
        tuple: (unit, precision) 例: ('1ns', '1ps')
               デフォルトは ('1ns', '1ps')
    """
```

**実行フロー**:
1. YAML の `timescale` フィールドをチェック（オーバーライド）
2. テストベンチファイルから `timescale` を抽出
3. RTL ファイルから `timescale` を抽出（フォールバック）
4. デフォルトの `1ns/1ps` を使用（最終フォールバック）

#### 4.4.3. TestRunner.validate_timescales() メソッド

すべてのソースファイル間でタイムスケールの整合性を検証します。

```python
def validate_timescales(self):
    """
    すべてのソースファイル間でタイムスケールの整合性を検証
    混在タイムスケールが検出された場合は警告を出力
    """
```

**動作**:
- テストベンチとすべての RTL ファイルのタイムスケールをチェック
- 異なるタイムスケールが見つかった場合、警告メッセージを表示
- テストベンチのタイムスケールが優先的に使用されることを通知

---

## 5. タイムアウト設定

このスクリプトは 2 種類のタイムアウトをサポートしています。

### 5.1. シミュレーションタイムアウト (`sim_timeout`)

**目的**: テストベンチ内のシミュレーション時間を制限

**設定場所**: `tests/test_config.yaml` の各テスト定義内

```yaml
- name: counter
  sim_timeout: "50us"  # 50 マイクロ秒
```

**処理**: `parse_sim_timeout()` 関数で数値に変換（**タイムスケール対応版**）

```python
def parse_sim_timeout(timeout_str, timescale_unit_str='1ns'):
    """
    Parse simulation timeout string and convert to numeric value in timescale units.

    ⭐ タイムスケール対応: テストベンチの実際のタイムスケールに基づいて正確に変換

    Examples:
        parse_sim_timeout("50us", "1ns")   -> 50000      (50μs = 50000 × 1ns)
        parse_sim_timeout("50us", "1ps")   -> 50000000   (50μs = 50000000 × 1ps)
        parse_sim_timeout("100ns", "1ps")  -> 100000     (100ns = 100000 × 1ps)
        parse_sim_timeout("1ms", "100fs")  -> 10000000000 (1ms = 10^10 × 100fs)

    Args:
        timeout_str: タイムアウト文字列 (例: "50us", "10000ns", "1ms")
        timescale_unit_str: SystemVerilog のタイムスケール単位 (例: "1ns", "1ps", "100fs")

    Returns:
        int: タイムスケール単位でのタイムアウト値（-GSIM_TIMEOUT パラメータ用）
    """
    # タイムアウト文字列を解析 (例: "50us" -> value=50, unit="us")
    timeout_match = re.match(r'^(\d+\.?\d*)\s*(fs|ps|ns|us|ms|s)$', timeout_str.strip())
    if not timeout_match:
        raise ValueError(f"Invalid sim_timeout format: {timeout_str}")

    timeout_value = float(timeout_match.group(1))
    timeout_unit = timeout_match.group(2)

    # タイムスケール単位を解析 (例: "1ns" -> coefficient=1, unit="ns")
    #                           "100fs" -> coefficient=100, unit="fs")
    timescale_match = re.match(r'^(\d+\.?\d*)\s*(fs|ps|ns|us|ms|s)$', timescale_unit_str.strip())
    if not timescale_match:
        raise ValueError(f"Invalid timescale format: {timescale_unit_str}")

    timescale_coefficient = float(timescale_match.group(1))
    timescale_unit = timescale_match.group(2)

    # 秒への変換係数
    time_to_seconds = {
        'fs': 1e-15,
        'ps': 1e-12,
        'ns': 1e-9,
        'us': 1e-6,
        'ms': 1e-3,
        's': 1.0
    }

    # タイムアウトを秒に変換
    timeout_seconds = timeout_value * time_to_seconds[timeout_unit]

    # タイムスケール単位を秒に変換（係数を考慮）
    timescale_seconds_per_unit = timescale_coefficient * time_to_seconds[timescale_unit]

    # タイムアウトに必要なタイムスケール単位数を計算
    result = timeout_seconds / timescale_seconds_per_unit

    # 整数として返す（浮動小数点精度問題を避けるため round() を使用）
    # 例: 49999.9999... → 50000
    return round(result)
```

**Verilator への渡し方**:

```python
# Add simulation timeout parameter if specified
if 'sim_timeout' in self.test_config:
    # ⭐ タイムスケール検証と自動検出
    self.validate_timescales()  # 混在警告を表示

    # テストベンチファイルからタイムスケールを自動検出
    timescale_unit, timescale_precision = self.get_effective_timescale()

    # タイムアウト文字列をタイムスケール単位の数値に変換
    sim_timeout_str = self.test_config['sim_timeout']
    sim_timeout_value = parse_sim_timeout(sim_timeout_str, timescale_unit)

    cmd.append(f"-GSIM_TIMEOUT={sim_timeout_value}")
    print(f"   Simulation timeout: {sim_timeout_str} → {sim_timeout_value} time units (timescale: {timescale_unit}/{timescale_precision})")
```

Verilator の `-G` オプションで `SIM_TIMEOUT` パラメータとしてテストベンチに渡されます。

**出力例**:
```
Simulation timeout: 50us → 50000 time units (timescale: 1ns/1ps)  # 低速モジュール
Simulation timeout: 100us → 100000000 time units (timescale: 1ps/1fs)  # 高速 SerDes
```

**テストベンチ側の対応**:

```systemverilog
module counter_tb #(
    parameter SIM_TIMEOUT = 50000  // Default 50us in ns
);
    // ...
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
        $finish;
    end
endmodule
```

### 5.2. 実行タイムアウト (`execution_timeout`)

**目的**: Verilator 実行ファイルの実行時間（実時間）を制限

**設定場所**: `tests/test_config.yaml` の `verilator` セクション

```yaml
verilator:
  execution_timeout: "30s"  # 30 秒
```

**処理**: `parse_timeout()` 関数で秒数に変換

```python
def parse_timeout(timeout_str):
    """
    Parse timeout string with unit suffix and convert to seconds.

    Supported formats:
        "50us"      -> 0.00005 seconds
        "10000ns"   -> 0.00001 seconds
        "100ms"     -> 0.1 seconds
        "5s"        -> 5.0 seconds
        50000 (int) -> interpret as microseconds (backward compatibility)
    """
    # Backward compatibility: if integer, treat as microseconds
    if isinstance(timeout_str, (int, float)):
        print(f"Warning: timeout_us (integer) is deprecated. Use timeout: \"{int(timeout_str)}us\" instead.")
        return timeout_str / 1_000_000  # Convert us to seconds

    # Parse string format
    if not isinstance(timeout_str, str):
        raise ValueError(f"Invalid timeout format: {timeout_str}")

    # Extract number and unit
    match = re.match(r'^(\d+\.?\d*)\s*(ns|us|ms|s)$', timeout_str.strip())
    if not match:
        raise ValueError(f"Invalid timeout format: {timeout_str}. Expected format: '<number><unit>' (e.g., '50us', '10000ns')")

    value = float(match.group(1))
    unit = match.group(2)

    # Convert to seconds
    conversions = {
        'fs': 1e-15,
        'ps': 1e-12,
        'ns': 1e-9,
        'us': 1e-6,
        'ms': 1e-3,
        's': 1.0
    }

    return value * conversions[unit]
```

**シミュレーション実行時の使用**:

```python
def run_simulation(self):
    """Execute the simulation"""
    print(f"🚀 Running simulation for '{self.test_name}'...")

    if not self.executable.exists():
        print(f"✗ Executable not found: {self.executable}")
        return False

    # Get execution timeout from verilator config (for freeze protection)
    timeout_seconds = None
    if 'execution_timeout' in self.verilator_config:
        timeout_seconds = parse_timeout(self.verilator_config['execution_timeout'])
        print(f"   Execution timeout: {self.verilator_config['execution_timeout']} ({timeout_seconds}s)")

    try:
        # Make sure waves directory exists
        self.waves_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [str(self.executable)],
            cwd=self.project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        # ...
    except subprocess.TimeoutExpired:
        print(f"✗ Simulation TIMEOUT (exceeded {timeout_seconds}s)")
        print(f"   The testbench may have an infinite loop or insufficient timeout value")
        return False
```

Python の `subprocess.run()` の `timeout` パラメータに渡されます。

### 5.3. タイムアウトの違いまとめ

| 項目 | シミュレーションタイムアウト | 実行タイムアウト |
|------|------------------------------|------------------|
| **意味** | シミュレーション内の時間 | 実世界の経過時間 |
| **単位** | timescale 依存（例: ns） | 秒 |
| **設定場所** | 各テストの `sim_timeout` | グローバルの `execution_timeout` |
| **目的** | テストシナリオの時間制限 | フリーズ防止 |
| **例** | `"50us"` → 50000 time units | `"30s"` → 30.0 seconds |

---

## 6. タイムスケール対応

### 6.1. 概要

**⭐ 新機能**: `run_test.py` は SystemVerilog の `timescale` ディレクティブを自動検出し、正確なタイムアウト変換を行います。

#### 6.1.1. 解決された問題

**以前の問題**: `parse_sim_timeout()` が常に `timescale 1ns/1ps` を仮定していたため、異なるタイムスケール（例: `timescale 1ps/1fs`）を使用する高速 SerDes モジュールでタイムアウト値が不正確になる致命的なバグがありました。

```python
# 🚨 旧実装の問題点
# timescale 1ps/1fs のテストベンチで：
#   sim_timeout: "50us" → 50000 に変換（誤り）
#   実際のタイムアウト: 50000ps = 0.05us（意図の 1000分の1！）
```

**新しい解決策**: ハイブリッドアプローチによる自動検出 + オプションのオーバーライド

### 6.2. 主な機能

#### 6.2.1. 自動タイムスケール検出

テストベンチファイルから `timescale` ディレクティブを自動的に読み取ります。

```python
def extract_timescale(sv_file_path):
    """
    SystemVerilog ファイルから timescale ディレクティブを解析

    Args:
        sv_file_path: SystemVerilog ファイルのパス

    Returns:
        tuple: (unit, precision) 例: ('1ns', '1ps'), ('1ps', '1fs')
               timescale が見つからない場合は (None, None)

    Examples:
        `timescale 1ns / 1ps  → ('1ns', '1ps')
        `timescale 1ps/1fs    → ('1ps', '1fs')
        `timescale 100fs/1fs  → ('100fs', '1fs')
    """
    try:
        with open(sv_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # `timescale <unit> / <precision> にマッチ
                # 空白のバリエーションと係数（例: 100fs）に対応
                match = re.match(r'`timescale\s+(\d+\.?\d*\s*\w+)\s*/\s*(\d+\.?\d*\s*\w+)', line.strip())
                if match:
                    unit = match.group(1).replace(' ', '')
                    precision = match.group(2).replace(' ', '')
                    return (unit, precision)
    except FileNotFoundError:
        print(f"Warning: File not found: {sv_file_path}")
    except Exception as e:
        print(f"Warning: Error reading {sv_file_path}: {e}")

    return (None, None)
```

#### 6.2.2. タイムスケール対応変換

検出されたタイムスケールに基づいて正確に変換します。

**変換例**:

| タイムアウト | タイムスケール | 計算 | 結果 |
|--------------|----------------|------|------|
| `"50us"` | `1ns/1ps` | 50μs ÷ 1ns | 50000 time units |
| `"50us"` | `1ps/1fs` | 50μs ÷ 1ps | 50000000 time units |
| `"100ns"` | `1ps/1fs` | 100ns ÷ 1ps | 100000 time units |
| `"1ms"` | `100fs/1fs` | 1ms ÷ 100fs | 10000000000 time units |

#### 6.2.3. 検証と警告

RTL ファイルとテストベンチで異なるタイムスケールが使用されている場合、警告を表示します。

```python
def validate_timescales(self):
    """
    すべてのソースファイル間でタイムスケールの整合性を検証
    混在タイムスケールが検出された場合は警告を出力
    """
    timescales = []

    # テストベンチをチェック
    tb_file = self.tb_dir / self.testbench_file
    tb_ts = extract_timescale(tb_file)
    if tb_ts != (None, None):
        timescales.append(('testbench', self.testbench_file, tb_ts[0]))

    # RTL ファイルをチェック
    for rtl_file in self.rtl_files:
        rtl_path = self.rtl_dir / rtl_file
        rtl_ts = extract_timescale(rtl_path)
        if rtl_ts != (None, None):
            timescales.append(('RTL', rtl_file, rtl_ts[0]))

    # 不整合をチェック
    if timescales:
        unique_timescales = set(ts[2] for ts in timescales)
        if len(unique_timescales) > 1:
            print(f"   ⚠️  WARNING: Mixed timescales detected in test '{self.test_name}':")
            for file_type, filename, ts in timescales:
                print(f"      {file_type:10s}: {filename:30s} → timescale {ts}")
            print(f"      Using testbench timescale for simulation timeout calculation")
```

**警告出力例**:
```
⚠️  WARNING: Mixed timescales detected in test 'serdes_integration'
   testbench : serdes_full_tb.sv              → timescale 1ps
   RTL       : counter.sv                     → timescale 1ns
   RTL       : tx_ffe.sv                      → timescale 1ps
   Using testbench timescale for simulation timeout calculation
```

#### 6.2.4. オプションの YAML オーバーライド

必要に応じて、YAML 設定で明示的にタイムスケールを指定できます。

```yaml
tests:
  - name: serdes_tx
    sim_timeout: "100us"
    timescale: "1ps"  # 自動検出をオーバーライド（高速 SerDes 用）
```

### 6.3. タイムスケール選択ガイドライン

設計の動作周波数に基づいて適切なタイムスケールを選択します：

#### 6.3.1. 低速モジュール (<1 GHz)
```systemverilog
`timescale 1ns / 1ps
```
- **用途**: カウンタ、ステートマシン、制御ロジック、一般的なデジタル回路
- **分解能**: 1 ナノ秒の時間単位、1 ピコ秒の精度
- **例**: 100 MHz システム（10ns 周期）は 1ns 分解能が必要

#### 6.3.2. 高速 SerDes (10-25 Gbps)
```systemverilog
`timescale 1ps / 1fs
```
- **用途**: FFE、DFE、CTLE、CDR、シリアライザ/デシリアライザ
- **分解能**: 1 ピコ秒の時間単位、1 フェムト秒の精度
- **例**: 25 Gbps システム（40ps ビット周期）は 1ps 分解能が必要

#### 6.3.3. 超高速 (>25 Gbps)
```systemverilog
`timescale 100fs / 1fs
```
- **用途**: ピコ秒以下の分解能が必要な設計
- **分解能**: 100 フェムト秒の時間単位、1 フェムト秒の精度
- **使用頻度**: 稀（超高速設計のみ）

### 6.4. 実際の使用例

#### 6.4.1. 例1: 低速モジュール（既存のテスト）

```yaml
# test_config.yaml
- name: counter
  sim_timeout: "50us"

# counter_tb.sv に記述
`timescale 1ns / 1ps

# 結果
# フレームワークが検出: 1ns timescale
# 計算: 50μs ÷ 1ns = 50000 time units
# 出力: Simulation timeout: 50us → 50000 time units (timescale: 1ns/1ps)
```

#### 6.4.2. 例2: 高速 SerDes FFE（将来のテスト）

```yaml
# test_config.yaml
- name: tx_ffe
  sim_timeout: "100us"
  testbench_file: tx/tx_ffe_tb.sv
  rtl_files:
    - tx/tx_ffe.sv

# tx_ffe_tb.sv に記述
`timescale 1ps / 1fs

# 結果
# フレームワークが検出: 1ps timescale
# 計算: 100μs ÷ 1ps = 100000000 time units
# 出力: Simulation timeout: 100us → 100000000 time units (timescale: 1ps/1fs)
```

#### 6.4.3. 例3: 係数付きタイムスケール

```yaml
# test_config.yaml
- name: ultra_fast
  sim_timeout: "1ms"

# ultra_fast_tb.sv に記述
`timescale 100fs / 1fs

# 結果
# フレームワークが検出: 100fs timescale
# 計算: 1ms ÷ 100fs = 10000000000 time units
# 出力: Simulation timeout: 1ms → 10000000000 time units (timescale: 100fs/1fs)
```

### 6.5. 浮動小数点精度の修正

タイムアウト計算で浮動小数点精度の問題が発生しないよう、`round()` を使用しています。

```python
# 🚨 以前の問題
timeout_seconds / timescale_seconds = 49999.99999999999
int(result) = 49999  # 切り捨てで不正確

# ✅ 修正後
timeout_seconds / timescale_seconds = 49999.99999999999
round(result) = 50000  # 正しい丸め
```

### 6.6. 実行時の検証

テストを実行して、正しいタイムスケール変換を確認できます：

```bash
uv run python3 scripts/run_test.py --test counter
```

**期待される出力**:
```
🔨 Compiling test 'counter' with Verilator...
   Simulation timeout: 50us → 50000 time units (timescale: 1ns/1ps)
   ✓ Compilation successful
```

出力には以下が表示されます：
- **入力**: `50us`（YAML から）
- **変換**: `50000 time units`（計算結果）
- **タイムスケール**: `1ns/1ps`（テストベンチから検出）

### 6.7. 移行ガイド

#### 6.7.1. 既存のテスト（変更不要）

既存のテストが `timescale 1ns/1ps` を使用している場合、変更は不要です：

```yaml
# tests/test_config.yaml（変更不要）
- name: counter
  sim_timeout: "50us"  # 自動的に動作
```

#### 6.7.2. SerDes モジュールの追加

ピコ秒タイムスケールを使用する SerDes モジュールを追加する場合：

1. **適切なタイムスケールでテストベンチを作成**:
```systemverilog
`timescale 1ps / 1fs  // 高速 SerDes

module tx_ffe_tb #(parameter SIM_TIMEOUT = 100000000);
  // テストベンチ実装
endmodule
```

2. **YAML 設定に追加**（自動検出が処理）:
```yaml
- name: tx_ffe
  sim_timeout: "100us"  # 自動的に 1ps を検出
  testbench_file: tx/tx_ffe_tb.sv
  rtl_files:
    - tx/tx_ffe.sv
```

3. **正しい変換を確認**:
```bash
uv run python3 scripts/run_test.py --test tx_ffe
# 期待: Simulation timeout: 100us → 100000000 time units (timescale: 1ps/1fs)
```

---

## 7. コマンドライン引数

### 7.1. 引数の定義

```python
def main():
    parser = argparse.ArgumentParser(
        description="Run SystemVerilog tests with Verilator (YAML-based)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all enabled tests
  python3 run_test.py --all

  # Run specific test
  python3 run_test.py --test counter --view

  # List available tests
  python3 run_test.py --list

  # Use custom config file
  python3 run_test.py --config my_tests.yaml --test counter
        """
    )

    parser.add_argument(
        "--config",
        default="tests/test_config.yaml",
        help="Path to YAML config file (default: tests/test_config.yaml)"
    )
    parser.add_argument(
        "--test",
        help="Run specific test by name"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all enabled tests"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available tests"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean simulation artifacts before running"
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Only clean artifacts, don't run tests"
    )
    parser.add_argument(
        "--view",
        action="store_true",
        help="Open GTKWave after simulation"
    )
```

### 7.2. 使用例

1. **テストリストの表示**:
   ```bash
   python3 scripts/run_test.py --list
   ```

2. **単一テストの実行**:
   ```bash
   python3 scripts/run_test.py --test counter
   ```

3. **波形ビューア付きで実行**:
   ```bash
   python3 scripts/run_test.py --test counter --view
   ```

4. **クリーンビルド**:
   ```bash
   python3 scripts/run_test.py --clean --test counter
   ```

5. **すべてのテストを実行**:
   ```bash
   python3 scripts/run_test.py --all
   ```

6. **クリーンアップのみ**:
   ```bash
   python3 scripts/run_test.py --clean-only --test counter
   ```

7. **カスタム設定ファイル**:
   ```bash
   python3 scripts/run_test.py --config custom_tests.yaml --test mytest
   ```

---

## 8. テストフロー

### 8.1. 完全な実行フロー

```python
def run(self, view=False):
    """Run complete test flow for this test"""
    print("=" * 70)
    print(f"  Test: {self.test_name}")
    if 'description' in self.test_config:
        print(f"  Description: {self.test_config['description']}")
    print("=" * 70)
    print()

    # Compile
    if not self.verilate():
        return False

    # Simulate
    if not self.run_simulation():
        return False

    # View waveform if requested
    if view and self.vcd_file.exists():
        self.view_waveform()

    return True
```

### 8.2. コンパイルフェーズ (`verilate()`)

```python
def verilate(self):
    """Compile SystemVerilog with Verilator"""
    print(f"🔨 Compiling test '{self.test_name}' with Verilator...")

    # Build command
    cmd = ["verilator"]

    # Add common flags
    cmd.extend(self.verilator_config.get('common_flags', []))

    # Add test-specific flags
    cmd.extend(self.test_config.get('verilator_extra_flags', []))

    # Add output directory
    cmd.extend(["-Mdir", str(self.obj_dir)])

    # Add top module
    cmd.extend(["--top-module", self.top_module])

    # Add RTL search path
    cmd.extend(["-y", str(self.rtl_dir)])

    # Add simulation timeout parameter if specified
    if 'sim_timeout' in self.test_config:
        sim_timeout_str = self.test_config['sim_timeout']
        sim_timeout_value = parse_sim_timeout(sim_timeout_str)
        cmd.append(f"-GSIM_TIMEOUT={sim_timeout_value}")
        print(f"   Simulation timeout: {sim_timeout_str} ({sim_timeout_value} time units)")

    # Add RTL files explicitly (supports subdirectory paths like tx/tx_ffe.sv)
    for rtl_file in self.rtl_files:
        rtl_path = self.rtl_dir / rtl_file
        cmd.append(str(rtl_path))

    # Add testbench file
    cmd.append(str(self.tb_dir / self.testbench_file))

    print(f"   Command: {' '.join(cmd)}")
```

**実行されるコマンド例**:
```bash
verilator --timing --binary --trace -Wno-TIMESCALEMOD \
  -Mdir sim/obj_dir \
  --top-module counter_tb \
  -y rtl \
  -GSIM_TIMEOUT=50000 \
  rtl/counter.sv \
  tb/counter_tb.sv
```

### 8.3. シミュレーションフェーズ (`run_simulation()`)

```python
def run_simulation(self):
    """Execute the simulation"""
    print(f"🚀 Running simulation for '{self.test_name}'...")

    if not self.executable.exists():
        print(f"✗ Executable not found: {self.executable}")
        return False

    # Get execution timeout from verilator config (for freeze protection)
    timeout_seconds = None
    if 'execution_timeout' in self.verilator_config:
        timeout_seconds = parse_timeout(self.verilator_config['execution_timeout'])
        print(f"   Execution timeout: {self.verilator_config['execution_timeout']} ({timeout_seconds}s)")

    try:
        # Make sure waves directory exists
        self.waves_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [str(self.executable)],
            cwd=self.project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # Check if VCD file was created
        if self.vcd_file.exists():
            vcd_size = self.vcd_file.stat().st_size
            print(f"✓ Simulation complete (VCD: {vcd_size} bytes)\n")
            return True
        else:
            print("⚠ VCD file not generated (may be normal for some tests)\n")
            return True  # Not necessarily a failure

    except subprocess.TimeoutExpired:
        print(f"✗ Simulation TIMEOUT (exceeded {timeout_seconds}s)")
        print(f"   The testbench may have an infinite loop or insufficient timeout value")
        return False

    except subprocess.CalledProcessError as e:
        print("✗ Simulation FAILED")
        print(f"\nStdout:\n{e.stdout}")
        print(f"\nStderr:\n{e.stderr}")
        return False
```

### 8.4. 波形表示フェーズ (`view_waveform()`)

```python
def view_waveform(self):
    """Open GTKWave to view waveform"""
    if not self.vcd_file.exists():
        print(f"✗ VCD file not found: {self.vcd_file}")
        return False

    print(f"📊 Opening GTKWave with {self.vcd_file}...")

    try:
        subprocess.Popen(
            ["gtkwave", str(self.vcd_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✓ GTKWave launched\n")
        return True

    except FileNotFoundError:
        print("✗ GTKWave not found. Please install gtkwave.")
        return False
```

### 8.5. テストサマリー

```python
# Print summary
if not args.clean_only and results:
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    for test_name, success in results.items():
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"  {test_name:30s} {status}")

    print("-" * 70)
    print(f"  Total: {len(results)}  |  Passed: {passed}  |  Failed: {failed}")
    print("=" * 70)

    return 0 if failed == 0 else 1
```

**出力例**:
```
======================================================================
  TEST SUMMARY
======================================================================
  counter                        ✓ PASSED
  demux_4bit                     ✓ PASSED
----------------------------------------------------------------------
  Total: 2  |  Passed: 2  |  Failed: 0
======================================================================
```

---

## 9. トラブルシューティング

### 9.1. PyYAML がインストールされていない

**エラー**:
```
Error: PyYAML is required. Install with: pip3 install pyyaml
```

**解決策**:
```bash
pip3 install pyyaml
# または uv を使用
uv sync
```

### 9.2. 設定ファイルが見つからない

**エラー**:
```
Error: Config file not found: tests/test_config.yaml
```

**解決策**:
- プロジェクトルートから実行していることを確認
- 設定ファイルのパスを `--config` オプションで指定

```bash
python3 scripts/run_test.py --config path/to/config.yaml
```

### 9.3. テストが見つからない

**エラー**:
```
Error: Test 'mytest' not found
Available tests: counter, demux_4bit
```

**解決策**:
- `--list` でテスト名を確認
- YAML ファイルでテストが定義されているか確認

```bash
python3 scripts/run_test.py --list
```

### 9.4. コンパイルエラー

**エラー**:
```
✗ Compilation FAILED
```

**解決策**:
- Verilator のエラーメッセージを確認
- RTL ファイルのパスが正しいか確認
- `verilator_extra_flags` で追加フラグが必要か確認

### 9.5. シミュレーションタイムアウト

**エラー**:
```
✗ Simulation TIMEOUT (exceeded 30.0s)
The testbench may have an infinite loop or insufficient timeout value
```

**解決策**:
- テストベンチに無限ループがないか確認
- `execution_timeout` の値を増やす
- `sim_timeout` の値を増やす

### 9.6. VCD ファイルが生成されない

**警告**:
```
⚠ VCD file not generated (may be normal for some tests)
```

**解決策**:
- テストベンチに `$dumpfile()` と `$dumpvars()` があるか確認
- ファイルパスが `sim/waves/{test_name}.vcd` と一致しているか確認

```systemverilog
initial begin
    $dumpfile("sim/waves/counter.vcd");
    $dumpvars(0, counter_tb);
end
```

### 9.7. GTKWave が起動しない

**エラー**:
```
✗ GTKWave not found. Please install gtkwave.
```

**解決策**:
```bash
sudo apt install gtkwave  # Ubuntu/Debian
```

### 9.8. タイムアウトが早すぎる／遅すぎる（タイムスケール関連）

**症状**:
- シミュレーションが期待より早く終了する
- タイムアウト値が不正確

**原因**:
テストベンチのタイムスケールが期待と異なる可能性があります。

**解決策**:
```bash
# テストベンチのタイムスケールを確認
grep "timescale" tb/your_testbench.sv

# 期待と異なる場合：
# 方法1: .sv ファイルを修正（推奨）
# 方法2: YAML で明示的にオーバーライド
```

**YAML でのオーバーライド例**:
```yaml
- name: your_test
  sim_timeout: "100us"
  timescale: "1ps"  # 自動検出をオーバーライド
```

### 9.9. タイムスケール混在の警告

**警告**:
```
⚠️  WARNING: Mixed timescales detected in test 'example'
   testbench : example_tb.sv → timescale 1ns
   RTL       : module_a.sv   → timescale 1ps
   Using testbench timescale for simulation timeout calculation
```

**原因**:
テストに含まれるファイルで異なるタイムスケールが使用されています。

**解決策**:
```bash
# すべてのタイムスケールを確認
grep -r "timescale" rtl/ tb/

# ベストプラクティス: 1つのテスト内では同じタイムスケールを使用
```

**設計ドメイン別の推奨タイムスケール**:
- 低速モジュール (<1 GHz): `timescale 1ns / 1ps`
- 高速 SerDes (10-25 Gbps): `timescale 1ps / 1fs`

### 9.10. タイムスケールが検出されない

**警告**:
```
Warning: No timescale found, defaulting to 1ns/1ps
```

**原因**:
.sv ファイルに `timescale` ディレクティブがありません。

**解決策**:
すべての .sv ファイルの先頭に `timescale` を追加：

```systemverilog
`timescale 1ns / 1ps  // ファイルの先頭に追加

module your_module;
  // モジュール実装
endmodule
```

---

## 10. まとめ

`run_test.py` は以下の機能を提供します：

✅ **YAML ベースのテスト管理**: 複数テストを設定ファイルで一元管理
✅ **自動化されたフロー**: コンパイル → シミュレーション → 波形表示
✅ **柔軟なタイムアウト**: シミュレーション時間と実行時間の両方を制御
✅ **⭐ タイムスケール自動検出**: SystemVerilog の `timescale` を自動的に認識して正確に変換
✅ **サブディレクトリ対応**: 階層的なプロジェクト構造をサポート
✅ **詳細なレポート**: テスト結果のサマリー表示

### 10.1. 新機能（タイムスケール対応）

- 🎯 **自動検出**: テストベンチから `timescale` を自動的に読み取り
- 🔄 **正確な変換**: タイムスケールに基づいてタイムアウトを正確に計算
- ⚠️ **検証機能**: 混在タイムスケールを警告
- 🛠️ **オーバーライド**: YAML で明示的に指定可能
- 🚀 **将来対応**: 高速 SerDes モジュール（`timescale 1ps/1fs`）に対応

このスクリプトを使用することで、SystemVerilog の検証作業を効率化できます。

---

## 11. 参考情報

### 11.1. YAML 設定ファイルの例

```yaml
project:
  rtl_dir: rtl
  tb_dir: tb
  sim_dir: sim
  obj_dir: sim/obj_dir
  waves_dir: sim/waves

verilator:
  common_flags:
    - --timing
    - --binary
    - --trace
    - -Wno-TIMESCALEMOD
  execution_timeout: "30s"

tests:
  - name: counter
    enabled: true
    description: "8-bit synchronous counter test"
    top_module: counter_tb
    testbench_file: counter_tb.sv
    rtl_files:
      - counter.sv
    verilator_extra_flags: []
    sim_timeout: "50us"
```

### 11.2. テストベンチのテンプレート

```systemverilog
`timescale 1ns / 1ps

module mymodule_tb #(
    parameter SIM_TIMEOUT = 50000  // Default timeout
);
    // VCD dump
    initial begin
        $dumpfile("sim/waves/mymodule.vcd");
        $dumpvars(0, mymodule_tb);
    end

    // Test sequence
    initial begin
        // Your test logic here

        $display("*** Test completed ***");
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
