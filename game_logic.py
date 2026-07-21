"""ESPERの山札・手札・捨て札・ターンなど、ゲーム状態を管理するモジュール。"""

# 山札をシャッフルするために使用する。
import random
# 手札に同じ種類のカードが何枚あるかを効率よく数えるために使用する。
from collections import Counter

class EsperGame:
    """1つの対戦部屋に対応するゲーム状態をまとめて保持するクラス。"""

    def __init__(self):
        """新しい対戦部屋用に、山札・手札・ターン情報を初期化する。"""
        # ゲームで使う7種類のカード名。
        self.types = ["千里眼", "時間移動", "念動力", "未来予知", "瞬間移動", "再生", "擬態"]
        # 各種類を8枚ずつ作るため、山札は7種類×8枚=56枚になる。
        self.deck = [c for c in self.types for _ in range(8)]
        # 毎回異なる配り方になるよう、ゲーム開始時に山札をランダム化する。
        random.shuffle(self.deck)
        
        # 山札の先頭3枚をゲームから除外する。
        # 内容はゲーム中は伏せ、ゲーム終了後に画面上で公開される。
        self.excluded_cards = self.deck[:3]
        self.deck = self.deck[3:]
        
        # pop()で山札の末尾から6枚ずつ取り、両プレイヤーの初期手札にする。
        self.p1_hand = [self.deck.pop() for _ in range(6)]
        self.p2_hand = [self.deck.pop() for _ in range(6)]
        
        # 捨て札は「能力発動などで同時に捨てたカード」を1組のリストとして管理する。
        # 例: [[カード1枚の組], [能力発動に使った2枚の組]]
        self.p1_discard_groups = []
        self.p2_discard_groups = []
        
        # 入室したプレイヤー名を、p1、p2の順で格納する。
        self.players = [] 
        
        # 能力の選択途中で使う一時データ。
        # temp_selection : 再生・千里眼で選んだカードの番号
        # regen_pool     : 再生で選択候補となる捨て札一覧
        # prescience_*   : 未来予知で確認中のカードと、選択済みの並び順
        self.temp_selection = []
        self.regen_pool = [] 
        self.prescience_cards = []
        self.prescience_ordered = []
        
        # 時間移動による追加ターンが予約されているかを表す。
        self.extra_turn = False
        # 先攻はp1。現在操作できるプレイヤーをこの値で判定する。
        self.current_turn = "p1"
        # UIの現在段階。2人目が入るまではWAITINGとする。
        self.turn_step = "WAITING"
        # 両プレイヤーの画面に表示する進行状況メッセージ。
        self.log_message = "対戦相手の入室を待っています..."

    def sort_hand(self, hand):
        """同種カードをまとめ、多い種類から表示する順番に手札を並べ替える。"""
        # Counterの例: ["再生", "再生", "擬態"] -> {"再生": 2, "擬態": 1}
        counts = Counter(hand)
        # 第1キーは枚数の降順、第2キーはカード名の昇順。
        # list(hand)を作るため、元の手札リスト自体の順番は変更しない。
        return sorted(list(hand), key=lambda x: (-counts[x], x))

    def check_esper(self, hand):
        """手札が「エスパー宣言」の条件（実質同種5枚）を満たすか判定する。"""
        counts = Counter(hand)
        mimic_count = counts.get("擬態", 0)
        # 擬態だけで5枚そろっている場合も達成扱い。
        if mimic_count >= 5: return True
        # 擬態は2枚につき、他のカード1枚分のワイルドカードとして扱う。
        # //は小数点以下を切り捨てる整数除算。
        wildcard_count = mimic_count // 2 
        for card, count in counts.items():
            # 擬態以外の各種類について、擬態による補助を足して5枚以上か調べる。
            if card != "擬態" and count + wildcard_count >= 5:
                return True
        # どの種類でも条件を満たさなかった場合は宣言不可。
        return False

    # roleに対応する手札を返す。UI側でp1/p2を意識せず共通処理するための関数。
    def get_hand(self, role): return self.p1_hand if role == "p1" else self.p2_hand

    # roleに対応する手札を、渡された新しいリストで置き換える。
    def set_hand(self, role, val):
        if role == "p1": self.p1_hand = val
        else: self.p2_hand = val

    # roleに対応する捨て札グループ一覧を返す。
    def get_discard_groups(self, role): return self.p1_discard_groups if role == "p1" else self.p2_discard_groups

    # 指定したプレイヤーの相手側roleを返す。
    def get_op_role(self, role): return "p2" if role == "p1" else "p1"

    def get_flat_discard(self, role):
        """グループ分けされた捨て札を、カード単位の1次元リストにして返す。"""
        groups = self.get_discard_groups(role)
        flat_list = []
        for group in groups:
            # extendはグループ内の要素を1つずつflat_listへ追加する。
            flat_list.extend(group)
        return flat_list

    def fill_hand_to_6(self, role):
        """山札がある限り、指定プレイヤーの手札が6枚になるまで補充する。"""
        hand = self.get_hand(role)
        # 山札が空の場合は、手札が6枚未満でもループを終了する。
        while len(hand) < 6 and self.deck:
            hand.append(self.deck.pop())

    def get_player_name(self, role):
        """roleに対応する入力済みの名前を返し、未入室なら仮の名前を返す。"""
        if role == "p1" and len(self.players) > 0: return self.players[0]
        if role == "p2" and len(self.players) > 1: return self.players[1]
        return f"プレイヤー{1 if role=='p1' else 2}"

    def trigger_endgame(self, reason):
        """通常の終了条件を処理し、手札の最大同種枚数で勝敗を決める。"""
        # 以降の操作を止め、UIをゲーム終了表示へ切り替える。
        self.turn_step = "GAME_OVER"
        # 各プレイヤーの手札を種類別に集計する。
        p1_counts = Counter(self.p1_hand)
        p2_counts = Counter(self.p2_hand)
        
        # 最も多く持っている同種カードの枚数。手札が空なら0枚とする。
        p1_max = max(p1_counts.values()) if p1_counts else 0
        # 最大枚数と同数の種類がいくつあるかを、同点時の第2判定に使う。
        p1_max_sets = sum(1 for v in p1_counts.values() if v == p1_max)
        
        p2_max = max(p2_counts.values()) if p2_counts else 0
        p2_max_sets = sum(1 for v in p2_counts.values() if v == p2_max)
        
        # 結果メッセージにはp1/p2ではなく、入力されたプレイヤー名を使う。
        p1_name = self.get_player_name("p1")
        p2_name = self.get_player_name("p2")
        
        msg = f"【終了】{reason}。"
        
        # 第1判定: 最大同種枚数が多いプレイヤーの勝利。
        if p1_max > p2_max:
            self.log_message = msg + f" 最大同種判定により、{p1_name} の勝利！🎉"
        elif p2_max > p1_max:
            self.log_message = msg + f" 最大同種判定により、{p2_name} の勝利！🎉"
        else:
            # 第2判定: 最大同種枚数が同じなら、その最大セットを多く持つ側の勝利。
            if p1_max_sets > p2_max_sets:
                self.log_message = msg + f" 同数({p1_max}枚)ですが、セット数({p1_max_sets}対{p2_max_sets})で {p1_name} の勝利！🎉"
            elif p2_max_sets > p1_max_sets:
                self.log_message = msg + f" 同数({p1_max}枚)ですが、セット数({p2_max_sets}対{p1_max_sets})で {p2_name} の勝利！🎉"
            else:
                # 第2判定まで同じ場合は引き分け。
                self.log_message = msg + " 最大同種もセット数も同じため、完全引き分け！⚖️"

    def trigger_draw(self, reason):
        """能力処理などが続行不能になった場合、理由付きで引き分け終了にする。"""
        self.turn_step = "GAME_OVER"
        self.log_message = f"⚖️【引き分け】{reason}⚖️"

    def end_action(self, current_role, action_msg=""):
        """1回の行動を終了し、終了判定または次ターンへの切替を行う。"""
        # 山札切れはゲーム全体の終了条件。
        if len(self.deck) == 0:
            self.trigger_endgame("山札が尽きました")
            return
        
        # どちらかの捨て札が18組に達した場合もゲーム全体を終了する。
        if len(self.p1_discard_groups) >= 18 or len(self.p2_discard_groups) >= 18:
            self.trigger_endgame("捨て札が18組（上限）に達しました")
            return
        
        if self.extra_turn:
            # 時間移動が発動済みなら手番を相手へ渡さず、現在のプレイヤーが続行する。
            # 追加ターンは1回だけなので、ここでフラグを戻す。
            self.extra_turn = False
            next_name = self.get_player_name(current_role)
            turn_msg = f"⏰ タイムリープ！続けて {next_name} の番です。"
            self.turn_step = "DISCARD"
        else:
            # 通常時は相手のroleへ手番を切り替える。
            self.current_turn = self.get_op_role(current_role)
            self.turn_step = "DISCARD"
            next_name = self.get_player_name(self.current_turn)
            turn_msg = f"【{next_name} のターン】カードを捨ててください。"
            
        # 能力結果などが渡された場合は、「今回の結果」と「次の手番」を1行にまとめる。
        if action_msg:
            self.log_message = f"{action_msg} ➔ {turn_msg}"
        else:
            self.log_message = turn_msg
