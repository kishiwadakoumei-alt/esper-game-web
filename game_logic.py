"""ESPERの山札・手札・捨て札・ターンなど、ゲーム状態を管理するモジュール。"""

import random
from collections import Counter
from datetime import datetime

class EsperGame:
    def __init__(self):
        # 念動力 -> 念力 に名称変更
        self.types = ["千里眼", "時間移動", "念力", "未来予知", "瞬間移動", "再生", "擬態"]
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
        self.clair_pool = [] # 千里眼用の候補プール
        self.prescience_cards = []
        self.prescience_ordered = []
        
        self.rematch_requests = set()
        self.extra_turn = False
        
        self.current_turn = "p1"
        self.turn_step = "WAITING"
        self.log_message = "対戦相手の入室を待っています..."
        
        self.chat_history = []
        # 時系列のログを保持するリスト
        self.log_history = []

    def sort_hand(self, hand):
        counts = Counter(hand)
        return sorted(list(hand), key=lambda x: (-counts[x], x))

    def check_esper(self, hand):
        counts = Counter(hand)
        mimic_count = counts.get("擬態", 0)
        if mimic_count >= 5: return True
        wildcard_count = mimic_count // 2 
        for card, count in counts.items():
            if card != "擬態" and count + wildcard_count >= 5:
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
        """時系列順にログを追加する。プレイヤー別の色分けのためroleも保存。"""
        time_str = datetime.now().strftime("%H:%M")
        name = self.get_player_name(role) if role else "システム"
        icon = "👤" if role == "p1" else ("🔴" if role == "p2" else "⚙️")
        self.log_history.append({"time": time_str, "role": role, "name": name, "icon": icon, "text": msg})
        self.log_message = msg

    def trigger_endgame(self, reason):
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
        if p1_sorted_counts > p2_sorted_counts:
            self.add_log(None, msg + f" 構成（{p1_set_str} 対 {p2_set_str}）により、{p1_name} の勝利！🎉")
        elif p2_sorted_counts > p1_sorted_counts:
            self.add_log(None, msg + f" 構成（{p2_set_str} 対 {p1_set_str}）により、{p2_name} の勝利！🎉")
        else:
            self.add_log(None, msg + f" 構成（お互い {p1_set_str}）が同じため、完全引き分け！⚖️")

    def trigger_draw(self, reason):
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
            self.turn_step = "DISCARD"
        else:
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
        
        # UI側で抽選演出を行うため、一時的に待機状態にする
        self.turn_step = "DECIDING_TURN"
        self.timer_started = False