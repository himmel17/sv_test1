# タイムスケール対応テストフレームワーク

## 1. 変更内容の概要

テストフレームワークに**タイムスケール自動検出機能**が追加され、SystemVerilog のタイムスケール設定に関係なく、シミュレーションタイムアウトを正確に処理できるようになりました。

### 1.1. 修正された問題

**問題点**: `parse_sim_timeout()` がすべてのテストベンチで `timescale 1ns/1ps` を使用していると仮定していたため、異なるタイムスケール（特に `timescale 1ps/1fs` を使用する高速 SerDes モジュール）を使用するファイルでタイムアウト計算が不正確になる重大なバグがありました。

**解決策**: 自動タイムスケール検出とオプションの YAML オーバーライドを備えたハイブリッドアプローチを実装しました。

## 2. 主な機能

1. **自動検出**: テストベンチファイルから `timescale` ディレクティブを読み取り
2. **正確な変換**: 検出されたタイムスケールに基づいて、タイムアウト文字列を適切な時間単位に変換
3. **検証**: RTL ファイルがテストベンチと異なるタイムスケールを持つ場合に警告
4. **オプションのオーバーライド**: エッジケース用に YAML で明示的な `timescale` フィールドをサポート

## 3. クイック例

### 3.1. 例1: 低速モジュール（既存のテスト）
```yaml
# test_config.yaml
sim_timeout: "50us"

# counter_tb.sv に記述: `timescale 1ns/1ps
# 結果: 50us → 50000 time units
# 出力: Simulation timeout: 50us → 50000 time units (timescale: 1ns/1ps)
```

### 3.2. 例2: 高速 SerDes（将来のテスト）
```yaml
# test_config.yaml
sim_timeout: "100us"

# tx_ffe_tb.sv に記述: `timescale 1ps/1fs
# 結果: 100us → 100000000 time units
# 出力: Simulation timeout: 100us → 100000000 time units (timescale: 1ps/1fs)
```

## 4. 実装の詳細

### 4.1. 新しい関数

1. **`extract_timescale(sv_file_path)`**
   - .sv ファイルから `timescale` を解析
   - 戻り値: `(unit, precision)` タプル

2. **`parse_sim_timeout(timeout_str, timescale_unit_str='1ns')`**
   - タイムスケール対応版（以前はナノ秒にハードコードされていました）
   - 浮動小数点精度のために `int()` の代わりに `round()` を使用
   - 係数をサポート（例: "100fs"）

3. **`TestRunner.get_effective_timescale()`**
   - テストベンチから自動検出
   - YAML オーバーライドをサポート
   - 1ns/1ps へのフォールバック

4. **`TestRunner.validate_timescales()`**
   - ファイル間の整合性をチェック
   - 混在タイムスケールの警告を表示

## 5. タイムスケールガイドライン

設計に適したタイムスケールを選択してください：

| 設計タイプ | クロック周波数 | タイムスケール | 例 |
|------------|---------------|---------------|-----|
| 低速       | <1 GHz        | `1ns/1ps`     | カウンタ、制御ロジック |
| 高速       | 10-25 Gbps    | `1ps/1fs`     | SerDes FFE/DFE/CTLE |
| 超高速     | >25 Gbps      | `100fs/1fs`   | 稀に必要 |

## 6. 検証

テストを実行して正しい動作を確認：

```bash
uv run python3 scripts/run_test.py --all
```

**期待される出力**:
```
🔨 Compiling test 'counter' with Verilator...
   Simulation timeout: 50us → 50000 time units (timescale: 1ns/1ps)
   ✓ Compilation successful

🔨 Compiling test 'demux_4bit' with Verilator...
   Simulation timeout: 10us → 10000 time units (timescale: 1ns/1ps)
   ✓ Compilation successful
```

## 7. 変更されたファイル

1. **scripts/run_test.py**
   - `extract_timescale()` 関数を追加
   - `parse_sim_timeout()` を書き直して任意のタイムスケールをサポート
   - TestRunner に `get_effective_timescale()` と `validate_timescales()` メソッドを追加
   - `verilate()` を更新して検出されたタイムスケールを使用

2. **CLAUDE.md**
   - 設計ドメイン別の包括的なタイムスケールガイドラインを追加
   - タイムスケールフィールドの説明を含む「新しいテストの追加」セクションを更新

3. **tests/test_config.yaml**
   - タイムスケール処理を説明する詳細なコメントを追加
   - オプションの `timescale` フィールドを示す例を追加

## 8. 移行ノート

- **既存のテスト**: 変更不要（後方互換性あり）
- **新しいテスト**: フレームワークが自動的にタイムスケール検出を処理
- **SerDes モジュール**: テストベンチファイルで `timescale 1ps/1fs` を使用

完全なガイドについては、`CLAUDE.md` と `tests/test_config.yaml` のコメントを参照してください。
