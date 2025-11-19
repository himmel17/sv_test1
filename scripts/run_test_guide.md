# run_test.py 使用ガイド

SystemVerilog テストベンチランナーの完全解説

## 目次

1. [概要](#概要)
2. [基本的な使い方](#基本的な使い方)
3. [アーキテクチャ](#アーキテクチャ)
4. [⭐ NEW: simulators.py - シミュレータ抽象化レイヤー](#-new-simulatorspy---シミュレータ抽象化レイヤー)
5. [主要なクラスと機能（run_test.py）](#主要なクラスと機能runtest.py)
6. [タイムアウト設定](#タイムアウト設定)
7. [タイムスケール対応](#タイムスケール対応)
8. [コマンドライン引数](#コマンドライン引数)
9. [テストフロー](#テストフロー)
10. [トラブルシューティング](#トラブルシューティング)
11. [まとめ](#まとめ)
12. [参考情報](#参考情報)

---

## 1. 概要

`run_test.py` は、SystemVerilog テストベンチを**複数のシミュレータ**（Verilator または Synopsys VCS）でコンパイル・実行し、GTKWave で波形を表示するための Python スクリプトです。

### 1.1. 主な特徴

- **⭐ NEW: マルチシミュレータ対応**: Verilator（オープンソース）と Synopsys VCS（商用）に対応
- **柔軟なシミュレータ選択**: コマンドライン、YAML 設定、テストごとの指定が可能
- **YAML ベース設定**: `tests/test_config.yaml` で複数のテストとシミュレータ設定を管理
- **抽象化レイヤー**: シミュレータ固有のロジックを分離し、拡張が容易
- **自動化されたフロー**: コンパイル → シミュレーション → 波形生成を一括実行
- **柔軟なタイムアウト制御**: シミュレーション時間と実行時間の両方を設定可能
- **サブディレクトリ対応**: RTL ファイルとテストベンチを階層的に管理

### 1.2. 対応シミュレータ

| シミュレータ | 種別 | 特徴 |
|------------|------|------|
| **Verilator** | オープンソース | 高速、無料、デフォルト設定 |
| **Synopsys VCS** | 商用 | 業界標準、高性能、ライセンス必要 |

**シミュレータ選択の優先順位**:
1. コマンドライン: `--simulator verilator|vcs`
2. テストごとの設定: YAML の `simulator: vcs`
3. グローバルデフォルト: YAML の `default_simulator: verilator`
4. フォールバック: `verilator`

### 1.3. 依存関係

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

import re

# ⭐ NEW: シミュレータ抽象化レイヤー
from simulators import SimulatorFactory
```

**必須ライブラリ**:
- **PyYAML**: YAML 設定ファイルの解析
- **simulators.py**: シミュレータ抽象化レイヤー（新規追加）

PyYAML がインストールされていない場合はエラーメッセージを表示して終了します。

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

### 2.6. ⭐ NEW: シミュレータ指定

```bash
# Verilator を使用（デフォルト）
python3 scripts/run_test.py --test counter

# VCS を使用
python3 scripts/run_test.py --test counter --simulator vcs

# すべてのテストを VCS で実行
python3 scripts/run_test.py --all --simulator vcs
```

**出力例**（シミュレータ表示）:
```
======================================================================
  Test: counter
  Description: 8-bit synchronous counter with overflow detection
  Simulator: vcs  ← 使用中のシミュレータが表示される
======================================================================
```

---

## 3. アーキテクチャ

### 3.1. ⭐ NEW: マルチシミュレータアーキテクチャ

スクリプトは**4 つの主要コンポーネント**で構成されています：

```
┌──────────────────────────────────────────────────────────┐
│  tests/test_config.yaml                                  │
│  - project.default_simulator: verilator/vcs              │
│  - simulators.verilator: {common_flags, ...}             │
│  - simulators.vcs: {common_flags, ...}                   │
│  - tests[].simulator: vcs (テストごとのオーバーライド)    │
└───────────────────────┬──────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────────────────┐
│  TestConfig クラス                                        │
│  - YAML の読み込みと解析                                  │
│  - simulators セクションの読み込み (⭐ NEW)              │
│  - 有効なテストのフィルタリング                           │
└───────────────────────┬──────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────────────────┐
│  TestRunner クラス (⭐ 大幅変更)                         │
│  - シミュレータタイプの決定                               │
│    (CLI > test config > project default > fallback)      │
│  - SimulatorFactory の呼び出し                            │
│  - シミュレータインスタンスへの処理委譲                   │
└───────────────────────┬──────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────────────────┐
│  SimulatorFactory (⭐ NEW)                               │
│  - シミュレータタイプに基づいて適切なインスタンスを生成   │
│  - Factory パターンによる抽象化                          │
└───────────────────────┬──────────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            v                       v
┌─────────────────────┐   ┌─────────────────────┐
│ VerilatorSimulator  │   │ VCSSimulator        │
│ (⭐ NEW)            │   │ (⭐ NEW)            │
│ - compile()         │   │ - compile()         │
│ - run_simulation()  │   │ - run_simulation()  │
│ - clean()           │   │ - clean()           │
│ - get_work_dir()    │   │ - get_work_dir()    │
│ - executable:       │   │ - executable:       │
│   V{module}         │   │   simv              │
└─────────────────────┘   └─────────────────────┘
```

**主な変更点**:
- ✅ `simulators.py` モジュールの追加（シミュレータ抽象化レイヤー）
- ✅ `TestRunner` からシミュレータ固有のロジックを分離
- ✅ Factory パターンによる柔軟なシミュレータ選択
- ✅ YAML 設定に `simulators` セクションを追加

### 3.2. データフロー

```
ユーザーコマンド
    │
    ├─ --simulator vcs (CLI オプション)
    │
    v
TestRunner.__init__()
    │
    ├─ シミュレータタイプ決定
    │   Priority: CLI > test config > project default > fallback
    │
    v
SimulatorFactory.create_simulator(type)
    │
    ├─ type='verilator' → VerilatorSimulator
    ├─ type='vcs'       → VCSSimulator
    │
    v
シミュレータインスタンス
    │
    ├─ compile(): verilator ... または vcs ...
    ├─ run_simulation(): ./V{module} または ./simv
    └─ clean(): obj_dir/ または vcs/ の削除
```

### 3.3. 実行例：完全なテストフロー

実際のコマンド実行時に、各コンポーネントがどのように連携するかを示します。

**実行コマンド**: `python3 run_test.py --test counter --view`

```
1. main() 開始
   ├─ 引数解析: test_name="counter", view=True, simulator=None
   ├─ YAML ロード: tests/test_config.yaml
   └─ "counter" テストの設定を取得

2. TestRunner インスタンス生成
   ├─ シミュレータタイプ決定:
   │  ├─ CLI: None (指定なし)
   │  ├─ テスト設定: None ('counter' には 'simulator' フィールドなし)
   │  ├─ グローバル設定: 'verilator'
   │  └─ → 'verilator' を使用
   │
   ├─ シミュレータ設定取得:
   │  └─ simulators.verilator から {common_flags: [...], execution_timeout: "30s"}
   │
   ├─ SimulatorFactory.create_simulator('verilator', ...) 呼び出し
   │  ├─ マッピング検索: 'verilator' → VerilatorSimulator クラス
   │  ├─ インスタンス化: VerilatorSimulator(project_root, ...)
   │  └─ return: VerilatorSimulator インスタンスを返す
   │
   └─ self.simulator = VerilatorSimulator インスタンス（保存）

3. TestRunner.run(view=True) 実行
   │
   ├─ [コンパイル]
   │  ├─ 出力: "🔨 Compiling test 'counter' with Verilator..."
   │  ├─ self.simulator.compile() 呼び出し
   │  │  └─ コマンド生成:
   │  │     verilator --binary --timing --trace -Wall \
   │  │       -Mdir sim/obj_dir --top-module counter_tb \
   │  │       -y rtl/ -GSIM_TIMEOUT=50000 \
   │  │       rtl/counter.sv tb/counter_tb.sv
   │  └─ 成果物: sim/obj_dir/Vcounter_tb (実行ファイル)
   │
   ├─ [シミュレーション]
   │  ├─ 出力: "🚀 Running simulation for 'counter'..."
   │  ├─ self.simulator.run_simulation() 呼び出し
   │  │  ├─ 実行可能ファイルチェック: sim/obj_dir/Vcounter_tb ✓
   │  │  ├─ waves ディレクトリ作成: mkdir -p sim/waves
   │  │  ├─ 実行: subprocess.run([sim/obj_dir/Vcounter_tb], timeout=30.0)
   │  │  ├─ テストベンチ動作:
   │  │  │  ├─ パラメータ: SIM_TIMEOUT=50000
   │  │  │  ├─ セルフチェックロジック実行
   │  │  │  ├─ VCD 出力: $dumpfile("sim/waves/counter.vcd")
   │  │  │  └─ 終了: $finish
   │  │  └─ 出力確認: sim/waves/counter.vcd ✓
   │  └─ 結果: True（成功）
   │
   └─ [波形表示]
      ├─ view=True かつ VCD 存在 ✓
      ├─ GTKWave 起動: subprocess.Popen(["gtkwave", "sim/waves/counter.vcd"])
      └─ バックグラウンドで実行

4. 結果サマリー出力
   ├─ === TEST SUMMARY ===
   ├─ counter           ✓ PASSED
   └─ Total: 1 | Passed: 1 | Failed: 0
```

**このフローから理解できること**:
- **シミュレータ選択**: 4段階の優先順位ロジックで決定（CLI → テスト設定 → グローバル設定 → フォールバック）
- **Factory パターン**: `SimulatorFactory` が適切なシミュレータインスタンスを動的に生成
- **抽象化の利点**: `TestRunner` はシミュレータ固有の詳細を知らず、`BaseSimulator` インターフェースのみに依存
- **ライフサイクル**: 構築（Factory生成） → コンパイル → シミュレーション → 波形表示の流れ

各コンポーネントの詳細については、[4. simulators.py - シミュレータ抽象化レイヤー](#4--new-simulatorspy---シミュレータ抽象化レイヤー) を参照してください。

---

## 4. ⭐ NEW: simulators.py - シミュレータ抽象化レイヤー

`scripts/simulators.py` は、異なるシミュレータ（Verilator, VCS）を統一的に扱うための抽象化レイヤーです。

### 4.1. BaseSimulator 抽象基底クラス

すべてのシミュレータが実装すべきインターフェースを定義します。

```python
from abc import ABC, abstractmethod
from pathlib import Path

class BaseSimulator(ABC):
    """シミュレータの抽象基底クラス"""

    def __init__(self, project_root, project_config, sim_config, test_config):
        """
        Args:
            project_root: プロジェクトルートパス
            project_config: プロジェクト設定（YAML の project セクション + simulators）
            sim_config: シミュレータ固有設定（YAML の simulators.verilator など）
            test_config: テスト設定（YAML の tests[] 要素）
        """
        self.project_root = Path(project_root)
        self.project_config = project_config
        self.sim_config = sim_config
        self.test_config = test_config

        # 共通パス
        self.rtl_dir = self.project_root / project_config.get('rtl_dir', 'rtl')
        self.tb_dir = self.project_root / project_config.get('tb_dir', 'tb')
        self.waves_dir = self.project_root / project_config.get('waves_dir', 'sim/waves')

        # テスト属性
        self.test_name = test_config['name']
        self.top_module = test_config['top_module']
        self.testbench_file = test_config['testbench_file']
        self.rtl_files = test_config.get('rtl_files', [])
        self.vcd_file = self.waves_dir / f"{self.test_name}.vcd"

    @abstractmethod
    def get_work_dir(self) -> Path:
        """シミュレータ固有の作業ディレクトリを返す"""
        pass

    @abstractmethod
    def get_executable_path(self) -> Path:
        """コンパイル済み実行ファイルのパスを返す"""
        pass

    @abstractmethod
    def compile(self) -> bool:
        """設計をコンパイルする (成功時 True)"""
        pass

    @abstractmethod
    def run_simulation(self) -> bool:
        """シミュレーションを実行する (成功時 True)"""
        pass

    @abstractmethod
    def clean(self):
        """シミュレータ固有の成果物をクリーンアップ"""
        pass
```

**共通機能**:
- `get_effective_timescale()`: テストベンチからタイムスケールを自動検出
- `validate_timescales()`: RTL とテストベンチのタイムスケール整合性検証

### 4.2. VerilatorSimulator クラス

Verilator 固有の実装です。

```python
class VerilatorSimulator(BaseSimulator):
    """Verilator シミュレータ実装"""

    def get_work_dir(self) -> Path:
        return self.project_root / self.project_config.get('obj_dir', 'sim/obj_dir')

    def get_executable_path(self) -> Path:
        # Verilator は "V{module}" という命名規則
        return self.get_work_dir() / f"V{self.top_module}"

    def compile(self) -> bool:
        """Verilator でコンパイル"""
        cmd = ["verilator"]

        # 共通フラグ (YAML から)
        cmd.extend(self.sim_config.get('common_flags', []))
        # 例: --binary, --timing, -Wall, --trace, -Wno-TIMESCALEMOD

        # テスト固有フラグ
        cmd.extend(self.test_config.get('verilator_extra_flags', []))

        # 出力ディレクトリ
        cmd.extend(["-Mdir", str(self.get_work_dir())])

        # トップモジュール
        cmd.extend(["--top-module", self.top_module])

        # RTL 検索パス
        cmd.extend(["-y", str(self.rtl_dir)])

        # シミュレーションタイムアウトパラメータ
        if 'sim_timeout' in self.test_config:
            timescale_unit, _ = self.get_effective_timescale()
            sim_timeout_value = parse_sim_timeout(
                self.test_config['sim_timeout'],
                timescale_unit
            )
            cmd.append(f"-GSIM_TIMEOUT={sim_timeout_value}")

        # RTL ファイル
        for rtl_file in self.rtl_files:
            cmd.append(str(self.rtl_dir / rtl_file))

        # テストベンチ
        cmd.append(str(self.tb_dir / self.testbench_file))

        # 実行
        result = subprocess.run(cmd, cwd=self.project_root, ...)
        return result.returncode == 0

    def run_simulation(self) -> bool:
        """Verilator 実行ファイルを実行"""
        executable = self.get_executable_path()  # V{module}
        timeout = parse_timeout(self.sim_config.get('execution_timeout', '30s'))

        result = subprocess.run(
            [str(executable)],
            cwd=self.project_root,
            timeout=timeout,
            ...
        )
        return result.returncode == 0

    def clean(self):
        """obj_dir/ と VCD ファイルを削除"""
        if self.get_work_dir().exists():
            shutil.rmtree(self.get_work_dir())
        if self.vcd_file.exists():
            self.vcd_file.unlink()
```

### 4.3. VCSSimulator クラス

Synopsys VCS 固有の実装です。

```python
class VCSSimulator(BaseSimulator):
    """Synopsys VCS シミュレータ実装"""

    def get_work_dir(self) -> Path:
        return self.project_root / self.project_config.get('vcs_dir', 'sim/vcs')

    def get_executable_path(self) -> Path:
        # VCS は常に "simv" という名前
        return self.get_work_dir() / "simv"

    def compile(self) -> bool:
        """VCS でコンパイル"""
        cmd = ["vcs"]

        # 共通フラグ (YAML から)
        cmd.extend(self.sim_config.get('common_flags', []))
        # 例: -sverilog, -timescale=1ns/1ps, -debug_access+all, +vcs+lic+wait, -full64

        # テスト固有フラグ
        cmd.extend(self.test_config.get('vcs_extra_flags', []))

        # 出力実行ファイル
        cmd.extend(["-o", str(self.get_executable_path())])

        # シミュレーションタイムアウトパラメータ
        if 'sim_timeout' in self.test_config:
            timescale_unit, _ = self.get_effective_timescale()
            sim_timeout_value = parse_sim_timeout(
                self.test_config['sim_timeout'],
                timescale_unit
            )
            # VCS は +define+ でパラメータを渡す
            cmd.append(f"+define+SIM_TIMEOUT={sim_timeout_value}")

        # RTL ファイル
        for rtl_file in self.rtl_files:
            cmd.append(str(self.rtl_dir / rtl_file))

        # テストベンチ
        cmd.append(str(self.tb_dir / self.testbench_file))

        # 実行
        result = subprocess.run(cmd, cwd=self.project_root, ...)
        return result.returncode == 0

    def run_simulation(self) -> bool:
        """VCS 実行ファイル (simv) を実行"""
        executable = self.get_executable_path()  # simv
        timeout = parse_timeout(self.sim_config.get('execution_timeout', '30s'))

        result = subprocess.run(
            [str(executable)],
            cwd=self.project_root,
            timeout=timeout,
            ...
        )
        return result.returncode == 0

    def clean(self):
        """vcs/, csrc/, simv.daidir/, ucli.key, VCD ファイルを削除"""
        if self.get_work_dir().exists():
            shutil.rmtree(self.get_work_dir())

        # VCS は追加の成果物を生成
        for artifact in ['csrc', 'simv.daidir', 'ucli.key']:
            path = self.project_root / artifact
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()

        if self.vcd_file.exists():
            self.vcd_file.unlink()
```

### 4.4. SimulatorFactory クラス

Factory パターンで適切なシミュレータインスタンスを生成します。

```python
class SimulatorFactory:
    """シミュレータインスタンスを生成するファクトリ"""

    @staticmethod
    def create_simulator(
        simulator_type: str,
        project_root,
        project_config,
        sim_config,
        test_config
    ) -> BaseSimulator:
        """
        Args:
            simulator_type: 'verilator' または 'vcs'
            ...

        Returns:
            適切なシミュレータインスタンス

        Raises:
            ValueError: 未知のシミュレータタイプ
        """
        simulators = {
            'verilator': VerilatorSimulator,
            'vcs': VCSSimulator
        }

        if simulator_type not in simulators:
            raise ValueError(
                f"Unknown simulator: {simulator_type}. "
                f"Available: {', '.join(simulators.keys())}"
            )

        return simulators[simulator_type](
            project_root, project_config, sim_config, test_config
        )
```

**使用例**:
```python
# TestRunner.__init__() 内で使用
simulator = SimulatorFactory.create_simulator(
    'vcs',  # または 'verilator'
    project_root,
    project_config,
    sim_config,
    test_config
)

# シミュレータインスタンスを使用
simulator.compile()
simulator.run_simulation()
simulator.clean()
```

#### 4.4.1. 役割とインスタンス生成フロー

**SimulatorFactory の目的**

`SimulatorFactory` は、テストフレームワークの中核を担うコンポーネントで、**シミュレータタイプ（`'verilator'` または `'vcs'`）に応じて適切なシミュレータインスタンスを動的に生成**します。この Factory パターンにより、以下の利点が得られます：

- **抽象化**: `TestRunner` はシミュレータ固有の実装詳細を知る必要がなく、`BaseSimulator` インターフェースのみに依存
- **拡張性**: 新しいシミュレータ（例：Icarus Verilog）を追加する場合、`BaseSimulator` を継承した新クラスと Factory のマッピング更新のみで対応可能
- **一元管理**: シミュレータインスタンスの生成ロジックが一箇所に集約され、保守性が向上

**シミュレータタイプの決定プロセス**

実際のシミュレータタイプは、以下の**4段階の優先順位**で決定されます（`TestRunner.__init__()` 内で実装）：

1. **コマンドライン引数** (最優先)
   ```bash
   python3 run_test.py --test counter --simulator vcs
   # → 強制的に VCS を使用
   ```

2. **テストごとの設定** (YAML の `simulator` フィールド)
   ```yaml
   tests:
     - name: high_speed_serdes
       simulator: vcs  # このテストのみ VCS を使用
   ```

3. **グローバルデフォルト** (YAML の `default_simulator`)
   ```yaml
   project:
     default_simulator: verilator  # 全テストのデフォルト
   ```

4. **ハードコードされたフォールバック**
   ```python
   simulator_type = simulator_type or 'verilator'  # 最終的なデフォルト
   ```

**実装コード（TestRunner.__init__() からの抜粋）**:
```python
# run_test.py の TestRunner.__init__() 内
if simulator_type is None:  # コマンドラインで指定されていない場合
    # テスト設定 → プロジェクトデフォルト → 'verilator' の順で決定
    simulator_type = test_config.get('simulator') or \
                   project_config.get('default_simulator', 'verilator')
```

**インスタンス生成から使用までの流れ**

`SimulatorFactory.create_simulator()` が呼ばれると、以下のステップが実行されます：

1. **マッピングによるクラス解決**
   ```python
   simulators = {
       'verilator': VerilatorSimulator,  # 文字列 → クラスへのマッピング
       'vcs': VCSSimulator
   }
   ```

2. **シミュレータタイプの検証**
   - 未知のタイプ（例：`'modelsim'`）の場合は `ValueError` を発生
   - 利用可能なシミュレータリストをエラーメッセージに含める

3. **インスタンス化とreturn**
   ```python
   return simulators[simulator_type](
       project_root, project_config, sim_config, test_config
   )
   # → VerilatorSimulator または VCSSimulator のインスタンスを返す
   # → 返却型は BaseSimulator（ポリモーフィズム）
   ```

4. **TestRunner でのインスタンス保存**
   ```python
   self.simulator = SimulatorFactory.create_simulator(...)
   # → self.simulator は BaseSimulator 型として扱われる
   ```

5. **ライフサイクル全体**
   ```
   [構築フェーズ] TestRunner.__init__()
     ↓
   SimulatorFactory.create_simulator() → VerilatorSimulator インスタンス
     ↓
   [実行フェーズ] TestRunner.run()
     ↓
   ├─ self.simulator.compile()          # Verilator でコンパイル
   ├─ self.simulator.run_simulation()   # Verilator で実行
   └─ GTKWave 起動（オプション）
     ↓
   [クリーンアップフェーズ] TestRunner.clean()
     ↓
   self.simulator.clean()               # sim/obj_dir/ と VCD を削除
   ```

**SimulatorFactory の動作例**

`TestRunner` 内での実際の使用方法：

```python
# TestRunner.__init__() 内でのシミュレータインスタンス生成
class TestRunner:
    def __init__(self, project_root, project_config, test_config, simulator_type=None):
        # シミュレータタイプ決定（4段階の優先順位）
        if simulator_type is None:
            simulator_type = test_config.get('simulator') or \
                           project_config.get('default_simulator', 'verilator')

        # SimulatorFactory を使用してインスタンス生成
        self.simulator = SimulatorFactory.create_simulator(
            simulator_type,      # 'verilator' または 'vcs'
            project_root,
            project_config,
            sim_config,
            test_config
        )
        # → self.simulator は BaseSimulator 型として扱われる
        #    実際には VerilatorSimulator または VCSSimulator インスタンス
```

**インスタンス生成の内部動作**:

1. **Factory 呼び出し**: `SimulatorFactory.create_simulator('verilator', ...)`
2. **マッピング検索**: 辞書 `simulators` から `'verilator'` → `VerilatorSimulator` クラスを取得
3. **インスタンス化**: `VerilatorSimulator(project_root, project_config, sim_config, test_config)`
4. **返却**: `BaseSimulator` 型として返される（ポリモーフィズム）
5. **保存**: `TestRunner` が `self.simulator` に保存し、以降のメソッドで使用

**使用時の抽象化の利点**:

```python
# TestRunner.run() 内
def run(self, view=False):
    # シミュレータの種類を意識せずに使用可能
    if not self.simulator.compile():     # VerilatorSimulator.compile() または VCSSimulator.compile()
        return False

    if not self.simulator.run_simulation():  # 同様に適切なメソッドが呼ばれる
        return False

    # TestRunner はシミュレータ固有のコマンドやパスを知らない
    # すべて BaseSimulator インターフェースを通じて実行
```

このように、**SimulatorFactory は単にインスタンスを生成するだけでなく、シミュレータ選択ロジックとテストフレームワーク全体を結びつける中心的な役割**を果たしています。

完全な実行フローについては、[3.3. 実行例：完全なテストフロー](#33-実行例完全なテストフロー) を参照してください。

### 4.5. Verilator vs VCS の違い

| 項目 | Verilator | VCS |
|------|-----------|-----|
| **実行ファイル名** | `V{top_module}` | `simv` |
| **コンパイルコマンド** | `verilator` | `vcs` |
| **パラメータ渡し** | `-GSIM_TIMEOUT=50000` | `+define+SIM_TIMEOUT=50000` |
| **主要フラグ** | `--binary`, `--timing`, `--trace` | `-sverilog`, `-debug_access+all`, `-full64` |
| **作業ディレクトリ** | `sim/obj_dir/` | `sim/vcs/` |
| **追加成果物** | なし | `csrc/`, `simv.daidir/`, `ucli.key` |
| **VCD ダンプ** | `--trace` フラグ | `-debug_access+all` フラグ |

---

## 5. 主要なクラスと機能（run_test.py）

### 5.1. TestConfig クラス

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

### 5.2. ⭐ 大幅変更: TestRunner クラス

個々のテストを実行するクラスです。**シミュレータ抽象化レイヤーを使用するように大幅変更**されました。

```python
class TestRunner:
    """Runs individual test cases using simulator abstraction"""

    def __init__(self, project_root, project_config, test_config, simulator_type=None):
        self.project_root = Path(project_root)
        self.project_config = project_config
        self.test_config = test_config

        # ⭐ NEW: シミュレータタイプの決定
        # 優先順位: CLI override > test config > project default > 'verilator'
        if simulator_type is None:
            simulator_type = test_config.get('simulator') or \
                           project_config.get('default_simulator', 'verilator')

        self.simulator_type = simulator_type

        # ⭐ NEW: シミュレータ固有設定の取得
        simulators_config = project_config.get('simulators', {})
        if simulator_type in simulators_config:
            sim_config = simulators_config[simulator_type]
        else:
            # 後方互換性: simulators セクションがない場合
            if simulator_type == 'verilator' and 'verilator' in project_config:
                sim_config = project_config['verilator']
            else:
                sim_config = {}

        # ⭐ NEW: SimulatorFactory でインスタンス生成
        self.simulator = SimulatorFactory.create_simulator(
            simulator_type,
            project_root,
            project_config,
            sim_config,
            test_config
        )

        # テスト属性（レポート用）
        self.test_name = test_config['name']
        self.vcd_file = self.simulator.vcd_file
```

**主な変更点**:

| 項目 | 旧実装 | 新実装 (⭐) |
|------|--------|------------|
| **初期化パラメータ** | `verilator_config` | `simulator_type=None` |
| **コンパイル** | `verilate()` メソッド | `simulator.compile()` へ委譲 |
| **シミュレーション** | `run_simulation()` メソッド | `simulator.run_simulation()` へ委譲 |
| **クリーンアップ** | `clean()` メソッド | `simulator.clean()` へ委譲 |
| **タイムスケール** | `get_effective_timescale()` | `simulator.get_effective_timescale()` へ移動 |
| **検証** | `validate_timescales()` | `simulator.validate_timescales()` へ移動 |

**残存メソッド**:
- `clean()`: シミュレータの `clean()` を呼び出す
- `view_waveform()`: GTKWave 起動（シミュレータ非依存）
- `run()`: 完全なテストフローを実行（シミュレータ使用）

**削除されたメソッド**:
- ❌ `verilate()`: `VerilatorSimulator.compile()` へ移動
- ❌ `run_simulation()`: `BaseSimulator.run_simulation()` へ移動
- ❌ `get_effective_timescale()`: `BaseSimulator.get_effective_timescale()` へ移動
- ❌ `validate_timescales()`: `BaseSimulator.validate_timescales()` へ移動

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

テストの有効なタイムスケールを決定します（自動検出アプローチ）。

```python
def get_effective_timescale(self):
    """
    このテストの有効なタイムスケールを決定

    戦略（自動検出のみ）:
    1. テストベンチファイルから自動検出
    2. フォールバック: RTL ファイルをチェック
    3. 最終フォールバック: デフォルトの ('1ns', '1ps')

    Returns:
        tuple: (unit, precision) 例: ('1ns', '1ps')
               デフォルトは ('1ns', '1ps')
    """
```

**実行フロー**:
1. テストベンチファイルから `timescale` を抽出
2. RTL ファイルから `timescale` を抽出（フォールバック）
3. デフォルトの `1ns/1ps` を使用（最終フォールバック）

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

**新しい解決策**: 自動検出アプローチによる正確なタイムスケール変換

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

**重要**: タイムスケールは常に自動検出されます。すべてのテストファイルで同じタイムスケールを使用することを推奨します。

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

  # ⭐ NEW: Use VCS simulator
  python3 run_test.py --test counter --simulator vcs
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
    parser.add_argument(
        "--simulator",
        choices=["verilator", "vcs"],
        help="Override simulator selection (default: from config)"
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

8. **⭐ NEW: シミュレータ指定**:
   ```bash
   # Verilator を使用（デフォルト）
   python3 scripts/run_test.py --test counter --simulator verilator

   # VCS を使用
   python3 scripts/run_test.py --test counter --simulator vcs

   # すべてのテストを VCS で実行
   python3 scripts/run_test.py --all --simulator vcs

   # VCS + 波形ビューア
   python3 scripts/run_test.py --test counter --simulator vcs --view
   ```

---

## 8. テストフロー

### 8.1. ⭐ 更新: 完全な実行フロー

TestRunner の `run()` メソッドは、シミュレータ抽象化レイヤーを使用して実行されます。

```python
def run(self, view=False):
    """Run complete test flow for this test"""
    print("=" * 70)
    print(f"  Test: {self.test_name}")
    if 'description' in self.test_config:
        print(f"  Description: {self.test_config['description']}")
    print(f"  Simulator: {self.simulator_type}")  # ⭐ NEW: 使用シミュレータを表示
    print("=" * 70)
    print()

    # ⭐ NEW: シミュレータインスタンスに委譲
    # Compile
    if not self.simulator.compile():
        return False

    # Simulate
    if not self.simulator.run_simulation():
        return False

    # View waveform if requested
    if view and self.vcd_file.exists():
        self.view_waveform()

    return True
```

**主な変更点**:
- `self.verilate()` → `self.simulator.compile()`: コンパイルをシミュレータに委譲
- `self.run_simulation()` → `self.simulator.run_simulation()`: シミュレーションをシミュレータに委譲
- シミュレータタイプを表示（verilator または vcs）

### 8.2. ⭐ 更新: コンパイルフェーズ

コンパイルは `BaseSimulator.compile()` インターフェースを通じて実行されます。実際の処理は各シミュレータクラスが実装します。

**Verilator の場合** (`VerilatorSimulator.compile()`):

```python
def compile(self):
    """Compile SystemVerilog with Verilator"""
    print(f"🔨 Compiling test '{self.test_name}' with Verilator...")

    # Build command
    cmd = ["verilator"]

    # Add common flags (from YAML simulators.verilator.common_flags)
    cmd.extend(self.sim_config.get('common_flags', []))
    # 例: --binary, --timing, -Wall, --trace, -Wno-TIMESCALEMOD

    # Add test-specific flags
    cmd.extend(self.test_config.get('verilator_extra_flags', []))

    # Add output directory
    cmd.extend(["-Mdir", str(self.get_work_dir())])

    # Add top module
    cmd.extend(["--top-module", self.top_module])

    # Add RTL search path
    cmd.extend(["-y", str(self.rtl_dir)])

    # Add simulation timeout parameter if specified
    if 'sim_timeout' in self.test_config:
        timescale_unit, _ = self.get_effective_timescale()
        sim_timeout_value = parse_sim_timeout(
            self.test_config['sim_timeout'],
            timescale_unit
        )
        cmd.append(f"-GSIM_TIMEOUT={sim_timeout_value}")  # Verilator 形式

    # Add RTL files and testbench
    for rtl_file in self.rtl_files:
        cmd.append(str(self.rtl_dir / rtl_file))
    cmd.append(str(self.tb_dir / self.testbench_file))

    # Execute compilation
    result = subprocess.run(cmd, cwd=self.project_root, ...)
    return result.returncode == 0
```

**VCS の場合** (`VCSSimulator.compile()`):

```python
def compile(self):
    """Compile SystemVerilog with VCS"""
    print(f"🔨 Compiling test '{self.test_name}' with VCS...")

    cmd = ["vcs"]

    # Add common flags (from YAML simulators.vcs.common_flags)
    cmd.extend(self.sim_config.get('common_flags', []))
    # 例: -sverilog, -timescale=1ns/1ps, -debug_access+all, +vcs+lic+wait, -full64

    # Add test-specific flags
    cmd.extend(self.test_config.get('vcs_extra_flags', []))

    # Output executable
    cmd.extend(["-o", str(self.get_executable_path())])  # simv

    # Add simulation timeout parameter if specified
    if 'sim_timeout' in self.test_config:
        timescale_unit, _ = self.get_effective_timescale()
        sim_timeout_value = parse_sim_timeout(
            self.test_config['sim_timeout'],
            timescale_unit
        )
        cmd.append(f"+define+SIM_TIMEOUT={sim_timeout_value}")  # VCS 形式

    # Add RTL files and testbench
    for rtl_file in self.rtl_files:
        cmd.append(str(self.rtl_dir / rtl_file))
    cmd.append(str(self.tb_dir / self.testbench_file))

    # Execute compilation
    result = subprocess.run(cmd, cwd=self.project_root, ...)
    return result.returncode == 0
```

**実行されるコマンド例**:

**Verilator**:
```bash
verilator --binary --timing -Wall --trace -Wno-TIMESCALEMOD \
  -Mdir sim/obj_dir \
  --top-module counter_tb \
  -y rtl \
  -GSIM_TIMEOUT=50000 \
  rtl/counter.sv \
  tb/counter_tb.sv
```

**VCS**:
```bash
vcs -sverilog -timescale=1ns/1ps -debug_access+all +vcs+lic+wait -full64 \
  -o sim/vcs/simv \
  +define+SIM_TIMEOUT=50000 \
  rtl/counter.sv \
  tb/counter_tb.sv
```

### 8.3. ⭐ 更新: シミュレーションフェーズ

シミュレーション実行も `BaseSimulator.run_simulation()` インターフェースを通じて行われます。

**共通実装** (VerilatorSimulator / VCSSimulator):

```python
def run_simulation(self):
    """Execute the simulation"""
    print(f"🚀 Running simulation for '{self.test_name}'...")

    executable = self.get_executable_path()  # ⭐ Verilator: V{module}, VCS: simv
    if not executable.exists():
        print(f"✗ Executable not found: {executable}")
        return False

    # Get execution timeout from simulator config (for freeze protection)
    timeout_seconds = None
    if 'execution_timeout' in self.sim_config:  # ⭐ simulator-specific config
        timeout_seconds = parse_timeout(self.sim_config['execution_timeout'])
        print(f"   Execution timeout: {self.sim_config['execution_timeout']} ({timeout_seconds}s)")

    try:
        # Make sure waves directory exists
        self.waves_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [str(executable)],
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

**主な変更点**:
- `self.executable` → `self.get_executable_path()`: シミュレータ固有のパス取得
- `self.verilator_config` → `self.sim_config`: シミュレータ非依存の設定参照

#### 8.3.1. ⭐ 更新: 実行ファイルの構築

実行ファイルパスは各シミュレータクラスの `get_executable_path()` メソッドで決定されます。

**Verilator の場合**:

```python
class VerilatorSimulator(BaseSimulator):
    def get_work_dir(self) -> Path:
        return self.project_root / self.project_config.get('obj_dir', 'sim/obj_dir')

    def get_executable_path(self) -> Path:
        # Verilator の命名規則: "V{top_module}"
        return self.get_work_dir() / f"V{self.top_module}"

# 実行例（counter テスト）
# top_module: counter_tb
# → 実行ファイル: sim/obj_dir/Vcounter_tb
```

**VCS の場合**:

```python
class VCSSimulator(BaseSimulator):
    def get_work_dir(self) -> Path:
        return self.project_root / self.project_config.get('vcs_dir', 'sim/vcs')

    def get_executable_path(self) -> Path:
        # VCS の命名規則: 常に "simv"
        return self.get_work_dir() / "simv"

# 実行例（counter テスト）
# top_module: counter_tb
# → 実行ファイル: sim/vcs/simv
```

**他のテストの例**:
- `demux_4bit` テスト:
  - Verilator: `sim/obj_dir/Vdemux_4bit_tb`
  - VCS: `sim/vcs/simv`
- `tx_ffe` テスト:
  - Verilator: `sim/obj_dir/Vtx_ffe_tb`
  - VCS: `sim/vcs/simv`

#### 8.3.2. ⭐ 更新: 実行されるコマンド

`subprocess.run([str(executable)], ...)` は各シミュレータの実行ファイルを起動します。

**Verilator の場合**:
```bash
# 作業ディレクトリ（cwd）: /home/rs133057/src/github.com/himmel17/sv_test1
# 実行コマンド:
./sim/obj_dir/Vcounter_tb
```

**VCS の場合**:
```bash
# 作業ディレクトリ（cwd）: /home/rs133057/src/github.com/himmel17/sv_test1
# 実行コマンド:
./sim/vcs/simv
```

**シェルで実行する場合の等価なコマンド**:
```bash
cd /home/rs133057/src/github.com/himmel17/sv_test1
./sim/obj_dir/Vcounter_tb  # Verilator
# または
./sim/vcs/simv              # VCS
```

**実行ファイルの特性**:
- **スタンドアロン実行ファイル**: 両シミュレータとも、単独で実行可能な実行ファイルを生成
- **引数不要**: 実行ファイルはパラメータなしで起動（シミュレーション設定はコンパイル時に埋め込み済み）
  - Verilator: `-GSIM_TIMEOUT=50000`
  - VCS: `+define+SIM_TIMEOUT=50000`
- **作業ディレクトリ**: `cwd=self.project_root` により、プロジェクトルートから実行
  - テストベンチ内の相対パス（`$dumpfile("sim/waves/counter.vcd")`）が正しく解決される

**実行例と出力**:
```bash
$ ./sim/obj_dir/Vcounter_tb  # Verilator
# または
$ ./sim/vcs/simv              # VCS

Time:     100 ns  Count: 01  Overflow: 0
Time:     200 ns  Count: 02  Overflow: 0
Time:     300 ns  Count: 03  Overflow: 0
...
Time:   25300 ns  Count: fd  Overflow: 0
Time:   25400 ns  Count: fe  Overflow: 0
Time:   25500 ns  Count: ff  Overflow: 1
Time:   25600 ns  Count: 00  Overflow: 0
*** PASSED: All tests passed successfully ***
```

**VCD ファイルの生成**:
実行ファイルが実行されると、テストベンチ内の以下のコードにより VCD ファイルが生成されます：

```systemverilog
// counter_tb.sv 内
initial begin
    $dumpfile("sim/waves/counter.vcd");  // 相対パスで指定
    $dumpvars(0, counter_tb);
end
```

作業ディレクトリがプロジェクトルートなので：
```
作業ディレクトリ: /home/rs133057/src/github.com/himmel17/sv_test1
相対パス: sim/waves/counter.vcd
→ 解決後の絶対パス: /home/rs133057/src/github.com/himmel17/sv_test1/sim/waves/counter.vcd
```

これは、シミュレータクラスで構築された `self.vcd_file` と一致します：
```python
self.vcd_file = self.waves_dir / f"{self.test_name}.vcd"
# 結果: /home/.../sv_test1/sim/waves/counter.vcd
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
- シミュレータのエラーメッセージを確認
- RTL ファイルのパスが正しいか確認
- Verilator: `verilator_extra_flags` で追加フラグが必要か確認
- VCS: `vcs_extra_flags` で追加フラグが必要か確認

**⭐ VCS 固有の問題**:
```
# VCS ライセンスエラー
✗ Error: VCS license not found
```
**解決策**: VCS ライセンスサーバーの設定を確認
```bash
# 環境変数の確認
echo $VCS_HOME
echo $LM_LICENSE_FILE
```

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

### 9.11. ⭐ NEW: VCS 実行ファイルが見つからない

**エラー**:
```
✗ Executable not found: sim/vcs/simv
```

**原因**:
VCS コンパイルが失敗したか、出力ディレクトリが間違っています。

**解決策**:
```bash
# VCS コンパイルログを確認
ls -la sim/vcs/

# コンパイルを再実行（詳細モード）
python3 scripts/run_test.py --test counter --simulator vcs

# 手動コンパイルでデバッグ
vcs -sverilog rtl/counter.sv tb/counter_tb.sv -o sim/vcs/simv
```

### 9.12. ⭐ NEW: VCS 成果物のクリーンアップ

VCS は Verilator よりも多くの成果物を生成します：
- `sim/vcs/` - 実行ファイル (simv)
- `csrc/` - C ソースコード
- `simv.daidir/` - シミュレーション情報
- `ucli.key` - ライセンスキー

**クリーンアップコマンド**:
```bash
python3 scripts/run_test.py --clean-only --test counter --simulator vcs
```

---

## 10. まとめ

`run_test.py` は以下の機能を提供します：

✅ **⭐ マルチシミュレータ対応**: Verilator と Synopsys VCS の両方に対応
✅ **柔軟なシミュレータ選択**: CLI、YAML 設定、テストごとの指定が可能
✅ **YAML ベースのテスト管理**: 複数テストを設定ファイルで一元管理
✅ **自動化されたフロー**: コンパイル → シミュレーション → 波形表示
✅ **柔軟なタイムアウト**: シミュレーション時間と実行時間の両方を制御
✅ **タイムスケール自動検出**: SystemVerilog の `timescale` を自動的に認識して正確に変換
✅ **サブディレクトリ対応**: 階層的なプロジェクト構造をサポート
✅ **詳細なレポート**: テスト結果のサマリー表示

### 10.1. ⭐ NEW: マルチシミュレータ対応

- 🔧 **抽象化レイヤー**: BaseSimulator、VerilatorSimulator、VCSSimulator による統一インターフェース
- 🏭 **Factory パターン**: SimulatorFactory による柔軟なシミュレータ生成
- 🎛️ **選択優先順位**: CLI > テスト設定 > グローバルデフォルト > フォールバック
- 📋 **YAML 設定**: simulators セクションでシミュレータ固有の設定を管理
- 🔄 **後方互換性**: 既存の verilator セクションもサポート

### 10.2. タイムスケール対応

- 🎯 **自動検出**: テストベンチから `timescale` を自動的に読み取り
- 🔄 **正確な変換**: タイムスケールに基づいてタイムアウトを正確に計算
- ⚠️ **検証機能**: 混在タイムスケールを警告
- 🛠️ **オーバーライド**: YAML で明示的に指定可能
- 🚀 **将来対応**: 高速 SerDes モジュール（`timescale 1ps/1fs`）に対応

このスクリプトを使用することで、SystemVerilog の検証作業を効率化できます。

---

## 11. 参考情報

### 11.1. ⭐ 更新: YAML 設定ファイルの例（マルチシミュレータ対応）

```yaml
project:
  rtl_dir: rtl
  tb_dir: tb
  sim_dir: sim
  obj_dir: sim/obj_dir      # Verilator 成果物
  vcs_dir: sim/vcs          # ⭐ NEW: VCS 成果物
  waves_dir: sim/waves
  default_simulator: verilator  # ⭐ NEW: グローバルデフォルト

# ⭐ NEW: シミュレータ固有の設定
simulators:
  verilator:
    common_flags:
      - --binary
      - --timing
      - -Wall
      - --trace
      - -Wno-TIMESCALEMOD
    execution_timeout: "30s"

  vcs:
    common_flags:
      - -sverilog
      - -timescale=1ns/1ps
      - -debug_access+all
      - +vcs+lic+wait
      - -full64
    execution_timeout: "30s"

# ⭐ 後方互換性: 旧形式の verilator セクションもサポート
# verilator:
#   common_flags: [...]
#   execution_timeout: "30s"

tests:
  - name: counter
    enabled: true
    description: "8-bit synchronous counter with overflow detection"
    top_module: counter_tb
    testbench_file: counter_tb.sv
    rtl_files:
      - counter.sv
    verilator_extra_flags: []
    vcs_extra_flags: []       # ⭐ NEW: VCS 固有フラグ
    sim_timeout: "50us"
    # simulator: vcs          # ⭐ NEW: テストごとのオーバーライド（オプション）

  - name: demux_4bit
    enabled: true
    description: "4-bit 1:4 demultiplexer"
    top_module: demux_4bit_tb
    testbench_file: demux_4bit_tb.sv
    rtl_files:
      - demux_4bit.sv
    verilator_extra_flags: []
    vcs_extra_flags: []
    sim_timeout: "10us"
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
