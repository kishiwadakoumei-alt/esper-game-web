import random
from collections import Counter

class EsperGame:
    def __init__(self):
        self.types = ["千里眼", "時間移動", "念動力", "未来予知", "瞬間移動", "再生", "擬態"]
        self.deck = [c for c in self.types for _ in range(8)]
        random.shuffle(self.deck)
        
        # ★追加：除外する3枚を専用のリストに保存
        self.excluded_cards = self.deck[:3]
        self.deck = self.deck[3:]
        
        self.p1_hand = [self.deck.pop() for _ in range(6)]
        self.p2_hand = [self.deck.pop() for _ in range(6)]
        
        self.p1_discard_groups = []
        self.p2_discard_groups = []
        
        self.players = [] 
        
        self.temp_selection = []
        self.regen_pool = [] 
        self.prescience_cards = []
        self.prescience_ordered = []
        
        self.extra_turn = False
        self.current_turn = "p1"
        self.turn_step = "WAITING"
        self.log_message = "対戦相手の入室を待っています..."

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
    def set_hand(self, role, val):
        if role == "p1": self.p1_hand = val
        else: self.p2_hand = val

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

    def trigger_endgame(self, reason):
        self.turn_step = "GAME_OVER"
        p1_counts = Counter(self.p1_hand)
        p2_counts = Counter(self.p2_hand)
        
        # ★修正：同種枚数が同じ場合の「セット数」での勝敗判定を追加
        p1_max = max(p1_counts.values()) if p1_counts else 0
        p1_max_sets = sum(1 for v in p1_counts.values() if v == p1_max)
        
        p2_max = max(p2_counts.values()) if p2_counts else 0
        p2_max_sets = sum(1 for v in p2_counts.values() if v == p2_max)
        
        msg = f"【終了】{reason}。"
        
        if p1_max > p2_max:
            self.log_message = msg + " 最大同種判定により、プレイヤー1の勝利！🎉"
        elif p2_max > p1_max:
            self.log_message = msg + " 最大同種判定により、プレイヤー2の勝利！🎉"
        else:
            if p1_max_sets > p2_max_sets:
                self.log_message = msg + f" 同数({p1_max}枚)ですが、セット数({p1_max_sets}対{p2_max_sets})でプレイヤー1の勝利！🎉"
            elif p2_max_sets > p1_max_sets:
                self.log_message = msg + f" 同数({p1_max}枚)ですが、セット数({p2_max_sets}対{p1_max_sets})でプレイヤー2の勝利！🎉"
            else:
                self.log_message = msg + " 最大同種もセット数も同じため、完全引き分け！⚖️"

    def trigger_draw(self, reason):
        self.turn_step = "GAME_OVER"
        self.log_message = f"⚖️【引き分け】{reason}⚖️"

    def end_action(self, current_role):
        if len(self.deck) == 0:
            self.trigger_endgame("山札が尽きました")
            return
        
        if len(self.p1_discard_groups) >= 18 or len(self.p2_discard_groups) >= 18:
            self.trigger_endgame("捨て札が18組（上限）に達しました")
            return
        
        if self.extra_turn:
            self.extra_turn = False
            self.log_message = f"⏰ タイムリープ！続けてプレイヤー{1 if current_role=='p1' else 2}の番です。"
            self.turn_step = "DISCARD"
        else:
            self.current_turn = self.get_op_role(current_role)
            self.turn_step = "DISCARD"
            self.log_message = f"プレイヤー{1 if self.current_turn=='p1' else 2}のターンです。カードを捨ててください。"