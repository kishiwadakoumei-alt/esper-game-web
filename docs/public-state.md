# ESPER 公開ゲーム状態

## 目的

`EsperGame` は山札や両プレイヤーの手札を保持するため、そのままブラウザへ送信してはならない。
`StateService.build_public_state()` は、閲覧者の役割に応じて秘匿情報を除外し、JSONへ変換可能な辞書を生成する。

## 基本方針

- 閲覧者は `p1` または `p2` に限定する。
- 自分の手札はカード名を公開する。
- 相手の手札は枚数だけ公開する。
- ゲーム終了時のみ相手の手札を公開する。
- 山札は枚数だけ公開し、カード内容は常に公開しない。
- 除外カードはゲーム終了時のみ公開する。
- 自分の裏向き捨て札はカード名を公開する。
- 相手の裏向き捨て札は `null` とし、表向きカードだけ名前を公開する。
- 能力処理中の一時情報は、操作中のプレイヤーだけに公開する。

## 主なレスポンス

```json
{
  "version": 1,
  "room_id": "sample-room",
  "viewer": {
    "role": "p1",
    "name": "Alice"
  },
  "game": {
    "turn_step": "DISCARD",
    "current_turn": "p1",
    "is_my_turn": true,
    "is_cpu": false,
    "deck_count": 41,
    "latest_log": "ゲーム開始",
    "finished": false
  },
  "opponent": {
    "role": "p2",
    "name": "Bob",
    "hand_count": 6,
    "hand": null
  },
  "my_hand": ["ヒーリング"],
  "discards": {
    "mine": [],
    "opponent": []
  },
  "excluded_cards": [null, null, null],
  "available_actions": ["discard_card"],
  "interaction": {
    "kind": "discard",
    "options": []
  },
  "logs": [],
  "chat": [],
  "rematch": {
    "requested_by_me": false,
    "requested_by_opponent": false
  }
}
```

## 能力の一時情報

### サイコキネシス

相手の手札選択肢には連番と表示名だけを含め、カード名は含めない。

### ヒーリング

自分のカードと表向きカードは名前を含める。相手の裏向きカード名は `null` にする。

### クレヤボヤンス

選択中はすべてのカード名を `null` にする。確認画面では、発動者にだけ選択したカード名を含める。

### プリサイエンス

閲覧したカードと指定済みの順番は発動者にだけ含める。相手のレスポンスでは `interaction` 自体を `null` にする。

## 操作候補

`available_actions` は現在のターン、ステップ、手札、山札枚数から、閲覧者が実行可能な操作だけを返す。

- 相手ターン中は通常操作を返さない。
- ESPER達成時は相手ターン中でも `declare_esper` を返す。
- ゲーム終了時は再戦と退出だけを返す。
- 山札不足で無効な能力しかない場合、能力発動アクションを返さない。

`interaction` は画面描画用の選択肢を返す。無効な選択肢は表示のため残し、`disabled` で区別する。

## テスト

`tests/test_state_service.py` では、状態全体をJSON文字列へ変換し、秘密カード名が含まれないことを検証する。

対象:

- 通常時の相手手札、山札、除外カード
- 表向き・裏向き捨て札
- ゲーム終了時の公開
- サイコキネシス
- ヒーリング
- クレヤボヤンス
- プリサイエンス
- ターン別の操作候補

この公開状態は第4段階で FastAPI と WebSocket のレスポンスに使用する。
