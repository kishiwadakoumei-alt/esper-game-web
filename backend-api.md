# バックエンドAPI

第4段階では、既存のゲームロジックとサービス層をFastAPIから利用できるようにした。
第5段階でブラウザ向けフロントエンドを追加し、同じFastAPIから配信している。

## 起動

```bash
python main.py
```

`main.py` は環境変数 `PORT` を使用し、未指定時は `8000` で起動する。

- OpenAPI: `http://localhost:8000/docs`
- ヘルスチェック: `GET /api/health`
- ブラウザ画面: `http://localhost:8000/`

## セッション

入室またはCPU戦作成のレスポンスに含まれる `token` を保存する。
以後のHTTPリクエストでは次のヘッダーを送る。

```http
Authorization: Bearer <token>
```

役割はクライアントから指定せず、サーバーがトークンに紐づく
`room_id` と `role` を解決する。セッションとルームは現段階では
プロセス内メモリに保存され、サーバー再起動時に消える。

## HTTPエンドポイント

| Method | Path | 説明 |
| --- | --- | --- |
| `POST` | `/api/rooms/join` | 対人ルームへ入室する |
| `POST` | `/api/rooms/cpu` | CPU対戦ルームを作る |
| `GET` | `/api/rooms/{room_id}/state` | 閲覧者用の公開状態を取得する |
| `POST` | `/api/rooms/{room_id}/actions` | ゲーム操作を実行する |
| `POST` | `/api/rooms/{room_id}/chat` | チャットを送信する |
| `POST` | `/api/rooms/{room_id}/rematch` | 再戦を要求する |
| `POST` | `/api/rooms/{room_id}/leave` | ルームを解散する |

入室:

```json
{
  "room_id": "sample-room",
  "name": "Alice"
}
```

CPU戦作成:

```json
{
  "name": "Alice",
  "level": "normal"
}
```

ゲーム操作:

```json
{
  "action": "discard_card",
  "payload": {
    "index": 0
  }
}
```

実行可能な操作は公開状態の `available_actions` に含まれるものだけである。
選択肢は `interaction` から取得する。サーバーは操作時にもターン、
手順、選択肢を再検証する。

対応する `action`:

- `declare_esper`
- `discard_card`
- `draw_hand`
- `open_ability_selection`
- `pass_turn`
- `cancel_ability_selection`
- `activate_ability`
- `open_mimic_selection`
- `cancel_mimic_selection`
- `activate_mimic`
- `select_teleport_target`
- `select_psychokinesis_discard`
- `select_psychokinesis_push`
- `toggle_healing_selection`
- `confirm_healing`
- `toggle_clairvoyance_selection`
- `confirm_clairvoyance`
- `finish_clairvoyance`
- `confirm_prescience_order`

## WebSocket

接続先:

```text
ws://localhost:8000/ws/rooms/{room_id}?token={token}
```

接続直後と状態更新時に、接続者専用の公開状態が届く。
`action_events` の文面も接続者向けに変換済みで、相手の伏せ情報は含まれない。

```json
{
  "type": "state",
  "data": {
    "version": 1
  }
}
```

生存確認として `{"type":"ping"}` を送ると
`{"type":"pong"}` が返る。ゲーム操作はHTTP APIへ送信し、
その結果は同じルームの各WebSocketへ、それぞれの役割に応じて
秘匿情報を除いた状態として配信される。

## 非同期処理

- 2人目の入室後、先攻抽選をバックグラウンドタスクで実行する。
- CPUのターンは1操作ずつ非同期に進行し、各操作後に状態を配信する。
- 同じルームへの更新はルーム単位のロックで直列化する。
- 退出およびアプリ終了時に、そのルームの未完了タスクを停止する。

## 現段階の制約

- 状態、セッション、WebSocket接続は単一プロセスのメモリ内にある。
- 複数ワーカー構成や再起動をまたぐ対戦継続には、RedisやDBなどの
  共有ストレージと分散ロックが必要になる。
- ブラウザ画面の構成は `docs/browser-frontend.md` を参照する。
