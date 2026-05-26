# Rust 移行設計ガイド

Pythonで実装された PRDMS4 を Rust に移行するにあたり、Rustの所有権モデル（Ownership）、借用規則（Borrowing）、並行処理モデルを考慮した大幅な設計変更が必要となります。本ドキュメントでは、移行の際の課題と具体的な解決策を提示します。

---

## 1. 循環参照と所有権の解決

### 課題：オブジェクトグラフの複雑さ
Python版の設計では、オブジェクト同士が双方向に参照し合っています。
- `Place`（区間）は現在専有している `Train`（列車）への参照を持つ。
- `Train` は自身が走る経路（`Place` のリスト）への参照を持つ。
- `TwoWayPoint` や `StopRail` などのデバイスは、関連する複数の `Place` への参照を持つ。

Rustでこれをそのまま参照（`&`）や `Arc` で実装しようとすると、以下の問題が発生します。
1. **循環参照によるメモリリーク**: `Arc` で相互参照すると参照カウントが 0 にならずメモリが解放されません。
2. **多重可変借用の禁止**: Rustでは「あるデータに対する可変の参照（`&mut`）は同時に1つしか存在できない」ため、ある区間の状態を変更しながら列車やポイントの状態を同時に書き換えることが極めて困難になります。

### 解決策：IDベースの参照（アリーナアロケータ / フラットデータ構造）
参照ポインタを直接持つのではなく、各オブジェクトを中央管理するマネージャー（または `HashMap` や `slotmap` 等のアリーナ）に格納し、オブジェクト間は単なる **Copy可能なID（インデックス）** で参照し合う構造に設計変更します。

```rust
// IDの定義
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct PlaceId(pub usize);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct TrainId(pub usize);

// 中央マネージャーによるデータ保持
pub struct PrdmsSystem {
    places: HashMap<PlaceId, Place>,
    trains: HashMap<TrainId, Train>,
}

// 構造体はIDのみを保持する
pub struct Place {
    pub id: PlaceId,
    pub occupier: Option<TrainId>, // ポインタではなくIDで保持
}
```
これにより、所有権の木構造がシンプルになり、Rustの借用チェッカーと完全に調和します。

---

## 2. 状態遷移とデッドロック防止 (トランザクションのRust化)

### 課題：複数リソースのロック取得順序
Python版の `OccupyTransaction` は、複数の `Place` の専有状態を一括で検証・変更します。
Rustで並行性を確保するために各 `Place` を `Arc<RwLock<Place>>` などで包む場合、異なるスレッドから複数の `Place` のロックを同時に取得しようとすると、**デッドロック**が発生するリスクがあります。
- スレッドAが Place 1 -> Place 2 の順でロックを取得しようとする。
- スレッドBが Place 2 -> Place 1 の順でロックを取得しようとする。
- -> お互いに相手のロック解放待ちになりデッドロック。

### 解決策：ロック取得順序の強制ソート
トランザクションを実行する前に、ロックを取得する `PlaceId` を常に**昇順にソート**してから順次ロックを取得するようにします。

```rust
impl OccupyTransaction {
    pub fn execute(&self, system: &mut PrdmsSystem) -> Result<(), CoreError> {
        // 1. ロック/書き換え対象のIDをソートしてデッドロックを防止する
        let mut target_ids: Vec<PlaceId> = self.operations.keys().cloned().collect();
        target_ids.sort(); 

        // 2. ソートされた順序で可変アクセスを取得して検証・更新
        for id in target_ids {
            let place = system.get_mut_place(id)?;
            // 検証および状態更新ロジック...
        }
        Ok(())
    }
}
```

---

## 3. 非同期並行処理とシリアル通信 (Tokioの導入)

### 課題：OSスレッドと非同期イベントループの分離
Python版ではシリアルI/O読み込みのために別スレッド (`threading.Thread`) を立ち上げ、メインの `asyncio` ループとの間でFutureオブジェクト（`asyncio.Future`）をやり取りしていました。

### 解決策：Tokioタスクとチャネル（`tokio::sync`）の利用
Rustでは、非同期ランタイム `tokio` と、非同期シリアル通信ライブラリ `tokio-serial` を採用することで、OSスレッドを手動で管理することなく、すべて軽量な非同期タスク（Green Thread）として統一的に扱えます。

```rust
use tokio::sync::{mpsc, oneshot};

// SerialWorkerをアクターモデルとして実装
pub struct SerialWorker {
    tx: mpsc::Sender<SerialCommand>,
}

pub struct SerialCommand {
    pub qid: String,
    pub cmd: String,
    pub response_tx: oneshot::Sender<String>, // レスポンス返却用のチャネル
}
```
- クエリの送信元は `oneshot::Sender` を作成してコマンドと一緒に送り、非同期にレスポンスを待機します。
- シリアル受信タスクがレスポンスパケットの `QID` を解析し、該当する `oneshot::Sender` へ結果を送信します。これにより、Pythonの `asyncio.Future` と同等の挙動をスレッドセーフかつ安全に実現できます。

---

## 4. エラー処理の移行

### 課題：クラス継承エラーから列挙型（Enum）への移行
Pythonでは `PRDMS4Error` -> `CoreError` -> `PlaceAlreadyOccupiedError` のように例外クラスを継承してエラーハンドリングを行っています。

### 解決策：`thiserror` を使ったカスタムEnumの定義
Rustでは例外の代わりに `Result<T, E>` を使います。エラー種別は列挙型で定義し、`thiserror` クレートを用いて実装を簡潔にします。

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CoreError {
    #[error("区間 {0:?} は既に他の列車に専有されています")]
    PlaceAlreadyOccupied(PlaceId),

    #[error("区間 {0:?} は専有されていません")]
    PlaceNotOccupied(PlaceId),

    #[error("ポイント安全制約違反")]
    PointSafetyViolation,
    
    #[error("シリアル通信エラー: {0}")]
    Serial(#[from] tokio_serial::Error),
}
```

---

## 5. 推奨されるクレート構成

移行にあたっては、以下のRust標準的なエコシステムを活用することを推奨します。

| カテゴリ | 推奨クレート | 用途 |
| :--- | :--- | :--- |
| **非同期ランタイム** | `tokio` | 非同期タスク管理、I/O、チャネル |
| **シリアル通信** | `tokio-serial` | 非同期でのシリアルポート読み書き |
| **Web APIフレームワーク** | `axum` | FastAPIの代替（ルート、ステータス提供） |
| **エラー定義** | `thiserror` | 構造化されたカスタムエラーの定義 |
| **ログ管理** | `tracing` | 非同期対応の構造化ロギング（Pythonの `logger` 代替） |
| **アリーナ型データ保持** | `slotmap` / `petgraph` | IDベースの区間・ネットワーク構造の構築に便利 |
