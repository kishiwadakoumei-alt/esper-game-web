import random
from collections import Counter

class EsperGame:
    def __init__(self):
        self.types = ["千里眼", "時間移動", "念動力", "未来予知", "瞬間移動", "再生", "擬態"]
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

    # プレイヤーの実際の名前を取得する関数
    def get_player_name(self, role):
        if role == "p1" and len(self.players) > 0: return self.players[0]
        if role == "p2" and len(self.players) > 1: return self.players[1]
        return f"プレイヤー{1 if role=='p1' else 2}"

    def trigger_endgame(self, reason):
        self.turn_step = "GAME_OVER"
        p1_counts = Counter(self.p1_hand)
        p2_counts = Counter(self.p2_hand)
        
        p1_max = max(p1_counts.values()) if p1_counts else 0
        p1_max_sets = sum(1 for v in p1_counts.values() if v == p1_max)
        
        p2_max = max(p2_counts.values()) if p2_counts else 0
        p2_max_sets = sum(1 for v in p2_counts.values() if v == p2_max)
        
        p1_name = self.get_player_name("p1")
        p2_name = self.get_player_name("p2")
        
        msg = f"【終了】{reason}。"
        
        if p1_max > p2_max:
            self.log_message = msg + f" 最大同種判定により、{p1_name} の勝利！🎉"
        elif p2_max > p1_max:
            self.log_message = msg + f" 最大同種判定により、{p2_name} の勝利！🎉"
        else:
            if p1_max_sets > p2_max_sets:
                self.log_message = msg + f" 同数({p1_max}枚)ですが、セット数({p1_max_sets}対{p2_max_sets})で {p1_name} の勝利！🎉"
            elif p2_max_sets > p1_max_sets:
                self.log_message = msg + f" 同数({p1_max}枚)ですが、セット数({p2_max_sets}対{p1_max_sets})で {p2_name} の勝利！🎉"
            else:
                self.log_message = msg + " 最大同種もセット数も同じため、完全引き分け！⚖️"

    def trigger_draw(self, reason):
        self.turn_step = "GAME_OVER"
        self.log_message = f"⚖️【引き分け】{reason}⚖️"

    # 詳細なアクションメッセージ（action_msg）を受け取れるように修正
    def end_action(self, current_role, action_msg=""):
        if len(self.deck) == 0:
            self.trigger_endgame("山札が尽きました")
            return
        
        if len(self.p1_discard_groups) >= 18 or len(self.p2_discard_groups) >= 18:
            self.trigger_endgame("捨て札が18組（上限）に達しました")
            return
        
        if self.extra_turn:
            self.extra_turn = False
            next_name = self.get_player_name(current_role)
            turn_msg = f"⏰ タイムリープ！続けて {next_name} の番です。"
            self.turn_step = "DISCARD"
        else:
            self.current_turn = self.get_op_role(current_role)
            self.turn_step = "DISCARD"
            next_name = self.get_player_name(self.current_turn)
            turn_msg = f"【{next_name} のターン】カードを捨ててください。"
            
        # 行動結果と次のターンの案内を合体させる
        if action_msg:
            self.log_message = f"{action_msg} ➔ {turn_msg}"
        else:
            self.log_message = turn_msg