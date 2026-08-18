"""ESPERの山札・手札・捨て札・ターンなど、ゲーム状態を管理するモジュール。

このモジュールはUIやHTTP APIを知らない、1ゲーム分の純粋な状態置き場です。
実際の操作手順や能力解決は services.game_service が担当し、ここでは
カード配布、手札補充、勝敗判定、ログ保存などの低レベルな状態更新だけを持ちます。
"""

import random
from collections import Counter
from datetime import datetime


class EsperGame:
    """1部屋に1つ作られる、ESPER対戦の進行状態。"""

    def __init__(self):
        """新しい対戦を初期山札・初期手札・待機状態で作成する。"""
        # 7種類×8枚で56枚の山札を作る。山札末尾を「一番上」としてpopする。
        self.types = ["クレヤボヤンス", "タイムリープ", "サイコキネシス", "プリサイエンス", "テレポート", "ヒーリング", "カモフラージュ"]
        self.deck = [c for c in self.types for _ in range(8)]
        random.shuffle(self.deck)

        # ゲーム外カードは最後まで公開しない。終局時だけ公開状態に含める。
        self.excluded_cards = self.deck[:3]
        self.deck = self.deck[3:]

        # 各プレイヤーの手札は常に実カード名で保持し、公開時だけ隠す。
        self.p1_hand = [self.deck.pop() for _ in range(6)]
        self.p2_hand = [self.deck.pop() for _ in range(6)]

        # 捨て札は能力コストなどで複数枚まとまるため、グループ配列で保持する。
        self.p1_discard_groups = []
        self.p2_discard_groups = []

        # 入室順のプレイヤー名。p1/p2の表示名解決に使う。
        self.players = []

        # 能力解決中の一時選択。ヒーリング、千里眼、未来予知などで共有する。
        self.temp_selection = []
        self.regen_pool = []
        self.clair_pool = []
        self.prescience_cards = []
        self.prescience_ordered = []

        # 再戦・追加ターン・終了結果など、ターン進行の補助状態。
        self.rematch_requests = set()
        self.extra_turn = False
        self.extra_turn_chain = 0
        self.turn_counts = {"p1": 0, "p2": 0}
        self.winner_role = None
        self.result_reason = None
        self.end_trigger_reason = None

        # CPU戦用のフラグ。cpu_actingは非同期CPU処理の多重起動を防ぐ。
        self.is_cpu = False
        self.cpu_acting = False

        # ルーム作成直後は2人目を待つ。入室完了後に先攻抽選へ進む。
        self.current_turn = "p1"
        self.turn_step = "WAITING"
        self.log_message = "対戦相手の入室を待っています..."

        # 画面へそのまま出す履歴。古い内容はフロント側で新しい順に並べる。
        self.chat_history = []
        self.log_history = []

        # ブラウザの中央通知用。イベントIDは再戦後も単調増加させる。
        self.action_event_sequence = 0
        self.action_events = []
        # 捨てたカードはdraw_hand時の通知で使うため、補充まで一時保持する。
        self.pending_discards = {}
        # カモフラージュ発動など、能力表示名に必要な直近能力情報。
        self.active_ability = None

    def add_action_event(
        self,
        actor_role,
        kind,
        title,
        detail_by_role=None,
        *,
        tone="ability",
        tone_by_role=None,
        duration_ms=2000,
    ):
        """閲覧者別の通知文を保存し、WebSocket経由で画面に流せるようにする。"""
        self.action_event_sequence += 1
        detail_by_role = detail_by_role or {}
        tone_by_role = tone_by_role or {}
        messages = {
            role: {
                "title": title,
                "detail": detail_by_role.get(role, ""),
                "tone": tone_by_role.get(role, tone),
            }
            for role in ("p1", "p2")
        }
        self.action_events.append({
            "id": self.action_event_sequence,
            "actor_role": actor_role,
            "kind": kind,
            "duration_ms": duration_ms,
            "messages": messages,
        })
        # 再接続時にも必要な直近分だけ残し、長時間プレイのメモリ増加を抑える。
        self.action_events = self.action_events[-100:]

    def sort_hand(self, hand):
        """同名カードが多い順、同数なら名前順に並べて手札を読みやすくする。"""
        counts = Counter(hand)
        return sorted(list(hand), key=lambda x: (-counts[x], x))

    def check_esper(self, hand):
        """同名5枚、またはカモフラージュ2枚=任意1枚換算でESPER成立を判定する。"""
        counts = Counter(hand)
        mimic_count = counts.get("カモフラージュ", 0)
        if mimic_count >= 5: return True
        wildcard_count = mimic_count // 2
        for card, count in counts.items():
            if card != "カモフラージュ" and count + wildcard_count >= 5:
                return True
        return False

    def get_hand(self, role): return self.p1_hand if role == "p1" else self.p2_hand

    def get_discard_groups(self, role): return self.p1_discard_groups if role == "p1" else self.p2_discard_groups

    def get_op_role(self, role): return "p2" if role == "p1" else "p1"

    def start_turn(self, role=None):
        """ターン開始回数を増やし、通知や短縮演出の判断材料にする。"""
        turn_role = role or self.current_turn
        self.turn_counts[turn_role] = self.turn_counts.get(turn_role, 0) + 1

    def get_flat_discard(self, role):
        """能力判定で扱いやすいよう、グループ化された捨て札を1枚ずつの配列に戻す。"""
        groups = self.get_discard_groups(role)
        flat_list = []
        for group in groups:
            flat_list.extend(group)
        return flat_list

    def fill_hand_to_6(self, role):
        """山札が残っている限り、対象プレイヤーの手札を6枚まで補充する。"""
        hand = self.get_hand(role)
        while len(hand) < 6 and self.deck:
            hand.append(self.deck.pop())

    def get_player_name(self, role):
        """未入室やテスト用状態でも表示名が欠けないように既定名を返す。"""
        if role == "p1" and len(self.players) > 0: return self.players[0]
        if role == "p2" and len(self.players) > 1: return self.players[1]
        return f"プレイヤー{1 if role=='p1' else 2}"

    def add_log(self, role, msg):
        """最新ログと履歴ログの両方へ、時刻・役割・表示アイコン付きで記録する。"""
        time_str = datetime.now().strftime("%H:%M")
        name = self.get_player_name(role) if role else "システム"
        icon = "👤" if role == "p1" else ("🔴" if role == "p2" else "⚙️")
        self.log_history.append({"time": time_str, "role": role, "name": name, "icon": icon, "text": msg})
        self.log_message = msg

    def trigger_endgame(self, reason):
        """山札切れなどの自動終了時に、ESPER優先で勝敗を確定する。"""
        self.extra_turn = False
        self.extra_turn_chain = 0
        self.winner_role = None
        self.result_reason = reason
        self.end_trigger_reason = reason
        self.turn_step = "GAME_OVER"
        p1_counts = Counter(self.p1_hand)
        p2_counts = Counter(self.p2_hand)

        # Pythonのリスト比較を使い、最大枚数、次点枚数...の順に手札構成を比べる。
        p1_sorted_counts = sorted(p1_counts.values(), reverse=True)
        p2_sorted_counts = sorted(p2_counts.values(), reverse=True)

        p1_name = self.get_player_name("p1")
        p2_name = self.get_player_name("p2")

        def format_sets(counts_list):
            return "・".join([f"{c}枚" for c in counts_list])

        p1_set_str = format_sets(p1_sorted_counts)
        p2_set_str = format_sets(p2_sorted_counts)

        msg = f"【終了】{reason}。"

        # 自動終了でもESPER成立者がいれば、通常の手札構成判定より優先する。
        p1_esper = self.check_esper(self.p1_hand)
        p2_esper = self.check_esper(self.p2_hand)

        if p1_esper and p2_esper:
            self.result_reason = "双方がESPER達成"
            self.add_log(None, msg + f" なんとお互いにESPER達成（{p1_set_str} 対 {p2_set_str}）のため、完全引き分け！⚖️")
        elif p1_esper:
            self.winner_role = "p1"
            self.result_reason = "ESPER達成"
            self.add_log(None, msg + f" 🌟【ESPER達成】{p1_name} が同種５枚を揃えていたため、{p1_name} の大勝利！🎉")
        elif p2_esper:
            self.winner_role = "p2"
            self.result_reason = "ESPER達成"
            self.add_log(None, msg + f" 🌟【ESPER達成】{p2_name} が同種５枚を揃えていたため、{p2_name} の大勝利！🎉")
        else:
            if p1_sorted_counts > p2_sorted_counts:
                self.winner_role = "p1"
                self.result_reason = "手札構成"
                self.add_log(None, msg + f" 構成（{p1_set_str} 対 {p2_set_str}）により、{p1_name} の勝利！🎉")
            elif p2_sorted_counts > p1_sorted_counts:
                self.winner_role = "p2"
                self.result_reason = "手札構成"
                self.add_log(None, msg + f" 構成（{p2_set_str} 対 {p1_set_str}）により、{p2_name} の勝利！🎉")
            else:
                self.result_reason = "完全引き分け"
                self.add_log(None, msg + f" 構成（お互い {p1_set_str}）が同じため、完全引き分け！⚖️")

    def trigger_draw(self, reason):
        """補充不能など、勝者を作らない終了条件を引き分けとして確定する。"""
        self.extra_turn = False
        self.extra_turn_chain = 0
        self.winner_role = None
        self.result_reason = reason
        self.end_trigger_reason = reason
        self.turn_step = "GAME_OVER"
        self.add_log(None, f"⚖️【引き分け】{reason}⚖️")

    def end_action(self, current_role, action_msg=""):
        """能力やパスの解決後、終局条件を確認して次のターンへ進める。"""
        if action_msg:
            self.add_log(current_role, action_msg)

        # ターン終了時に山札や捨て札上限を確認し、条件に達していれば即判定へ入る。
        if len(self.deck) == 0:
            self.trigger_endgame("山札が尽きました")
            return

        if len(self.p1_discard_groups) >= 18 or len(self.p2_discard_groups) >= 18:
            self.trigger_endgame("捨て札が18組（上限）に達しました")
            return

        if self.extra_turn:
            self.extra_turn = False
            self.extra_turn_chain += 1
            self.turn_step = "DISCARD"
        else:
            self.extra_turn_chain = 0
            self.current_turn = self.get_op_role(current_role)
            self.turn_step = "DISCARD"
        self.start_turn(self.current_turn)

    def reset_game(self):
        """同じ部屋・同じプレイヤー名のまま、再戦用にゲーム状態だけ作り直す。"""
        self.deck = [c for c in self.types for _ in range(8)]
        random.shuffle(self.deck)

        self.excluded_cards = self.deck[:3]
        self.deck = self.deck[3:]

        self.p1_hand = [self.deck.pop() for _ in range(6)]
        self.p2_hand = [self.deck.pop() for _ in range(6)]

        self.p1_discard_groups = []
        self.p2_discard_groups = []

        self.temp_selection = []
        self.regen_pool = []
        self.clair_pool = []
        self.prescience_cards = []
        self.prescience_ordered = []

        self.rematch_requests = set()
        self.extra_turn = False
        self.extra_turn_chain = 0
        self.turn_counts = {"p1": 0, "p2": 0}
        self.winner_role = None
        self.result_reason = None
        self.end_trigger_reason = None

        self.turn_step = "DECIDING_TURN"
        self.timer_started = False
        self.cpu_acting = False
        self.pending_discards = {}
        self.active_ability = None
        self.action_events = []
