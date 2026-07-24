"""ESPERの山札・手札・捨て札・ターンなど、ゲーム状態を管理するモジュール。"""

import random
from collections import Counter
from datetime import datetime

class EsperGame:
    def __init__(self):
        self.types = ["クレヤボヤンス", "タイムリープ", "サイコキネシス", "プリサイエンス", "テレポート", "ヒーリング", "カモフラージュ"]
        self.deck = [c for c in self.types for _ in range(8)]
        random.shuffle(self.deck)
        
        self.excluded_cards = self.deck[:3]
        self.deck = self.deck[3:]
        
        self.p1_hand = [self.deck.pop() for _ in range(6)]
        self.p2_hand = [self.deck.pop() for _ in range(6)]
        
        self.p1_discard_groups = []
        self.p2_discard_groups = []
        
        self.players = [] 
        
        self.temp_selection = []
        self.regen_pool = [] 
        self.clair_pool = [] 
        self.prescience_cards = []
        self.prescience_ordered = []
        
        self.rematch_requests = set()
        self.extra_turn = False
        self.extra_turn_chain = 0
        
        # CPU戦用のフラグ
        self.is_cpu = False
        self.cpu_acting = False
        
        self.current_turn = "p1"
        self.turn_step = "WAITING"
        self.log_message = "対戦相手の入室を待っています..."
        
        self.chat_history = []
        self.log_history = []

        # ブラウザの中央通知用。イベントIDは再戦後も単調増加させる。
        self.action_event_sequence = 0
        self.action_events = []
        self.pending_discards = {}
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
        self.action_events = self.action_events[-100:]

    def sort_hand(self, hand):
        counts = Counter(hand)
        return sorted(list(hand), key=lambda x: (-counts[x], x))

    def check_esper(self, hand):
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

    def get_flat_discard(self, role):
        groups = self.get_discard_groups(role)
        flat_list = []
        for group in groups:
            flat_list.extend(group)
        return flat_list

    def fill_hand_to_6(self, role):
        hand = self.get_hand(role)
        while len(hand) < 6 and self.deck:
            hand.append(self.deck.pop())

    def get_player_name(self, role):
        if role == "p1" and len(self.players) > 0: return self.players[0]
        if role == "p2" and len(self.players) > 1: return self.players[1]
        return f"プレイヤー{1 if role=='p1' else 2}"

    def add_log(self, role, msg):
        time_str = datetime.now().strftime("%H:%M")
        name = self.get_player_name(role) if role else "システム"
        icon = "👤" if role == "p1" else ("🔴" if role == "p2" else "⚙️")
        self.log_history.append({"time": time_str, "role": role, "name": name, "icon": icon, "text": msg})
        self.log_message = msg

    def trigger_endgame(self, reason):
        self.extra_turn = False
        self.extra_turn_chain = 0
        self.turn_step = "GAME_OVER"
        p1_counts = Counter(self.p1_hand)
        p2_counts = Counter(self.p2_hand)
        
        p1_sorted_counts = sorted(p1_counts.values(), reverse=True)
        p2_sorted_counts = sorted(p2_counts.values(), reverse=True)
        
        p1_name = self.get_player_name("p1")
        p2_name = self.get_player_name("p2")
        
        def format_sets(counts_list):
            return "・".join([f"{c}枚" for c in counts_list])
            
        p1_set_str = format_sets(p1_sorted_counts)
        p2_set_str = format_sets(p2_sorted_counts)
        
        msg = f"【終了】{reason}。"

        p1_esper = self.check_esper(self.p1_hand)
        p2_esper = self.check_esper(self.p2_hand)

        if p1_esper and p2_esper:
            self.add_log(None, msg + f" なんとお互いにESPER達成（{p1_set_str} 対 {p2_set_str}）のため、完全引き分け！⚖️")
        elif p1_esper:
            self.add_log(None, msg + f" 🌟【ESPER達成】{p1_name} が同種５枚を揃えていたため、{p1_name} の大勝利！🎉")
        elif p2_esper:
            self.add_log(None, msg + f" 🌟【ESPER達成】{p2_name} が同種５枚を揃えていたため、{p2_name} の大勝利！🎉")
        else:
            if p1_sorted_counts > p2_sorted_counts:
                self.add_log(None, msg + f" 構成（{p1_set_str} 対 {p2_set_str}）により、{p1_name} の勝利！🎉")
            elif p2_sorted_counts > p1_sorted_counts:
                self.add_log(None, msg + f" 構成（{p2_set_str} 対 {p1_set_str}）により、{p2_name} の勝利！🎉")
            else:
                self.add_log(None, msg + f" 構成（お互い {p1_set_str}）が同じため、完全引き分け！⚖️")

    def trigger_draw(self, reason):
        self.extra_turn = False
        self.extra_turn_chain = 0
        self.turn_step = "GAME_OVER"
        self.add_log(None, f"⚖️【引き分け】{reason}⚖️")

    def end_action(self, current_role, action_msg=""):
        if action_msg:
            self.add_log(current_role, action_msg)
            
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

    def reset_game(self):
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
        
        self.turn_step = "DECIDING_TURN"
        self.timer_started = False
        self.cpu_acting = False
        self.pending_discards = {}
        self.active_ability = None
        self.action_events = []