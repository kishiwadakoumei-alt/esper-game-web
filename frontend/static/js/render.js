const PHASE_MESSAGES = {
  WAITING: "対戦相手の入室を待っています。あいことばを友達に共有してください。",
  DECIDING_TURN: "先攻・後攻を抽選しています…",
  DISCARD: "手札から1枚選んで捨てます。",
  DRAW: "山札からカードを1枚引きます。",
  THINK: "新しい手札を確認し、能力を使うかターンを終えるか選びます。",
  ABILITY: "発動する能力を選んでください。",
  MIMIC_SELECTION: "カモフラージュで発動する能力を選んでください。",
  TELEPORT_SELECTION: "相手の手札から捨てさせる能力カードを宣言してください。",
  PSY_DISCARD_SELECTION: "相手の手札から捨てさせるカードを選んでください。",
  PSY_PUSH_SELECTION: "相手の裏向きの捨て札から、手札へ戻す1枚を選んでください。",
  REGEN_SELECTION: "山札へ戻す場札を3枚まで選んでください。",
  CLAIR_SELECTION: "中身を見るカードを2枚まで選んでください。",
  CLAIR_REVEAL: "透視結果を確認してください。",
  PRESCIENCE_SELECT_1: "山札の一番上にするカードを選んでください。",
  PRESCIENCE_SELECT_2: "山札の上から2番目にするカードを選んでください。",
  GAME_CLEAR: "ESPER達成。勝負が決まりました。",
  GAME_OVER: "ゲーム終了。公開された結果を確認してください。",
  ROOM_DISBANDED: "対戦相手が退出し、ルームが解散されました。",
};

const CARD_EFFECTS = {
  クレヤボヤンス:
    "相手の手札または相手の場にある裏向きのカードから、2枚まで選んで内容を確認します。",
  タイムリープ:
    "このターンの終了後、もう一度自分のターンを行います。追加ターンでも能力を使用できます。",
  サイコキネシス:
    "相手の手札を1枚捨てさせ、相手の裏向きの捨て札から1枚を手札へ戻します。",
  プリサイエンス:
    "山札の上から3枚を見て、好きな順番に並べ替えて山札の上へ戻します。",
  テレポート:
    "能力を1つ宣言し、相手の手札にあるその能力のカードをすべて捨てさせます。",
  ヒーリング:
    "場にあるカードを3枚まで選び、山札へ加えてシャッフルします。",
  カモフラージュ:
    "このターン中のみ好きなカード1枚として使えます。そのカードで能力を発動でき、ESPER宣言にも使用できます。",
};

function byId(id) {
  return document.getElementById(id);
}

function clear(node) {
  node.replaceChildren();
}

function create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

function emptyNote(text = "まだありません") {
  return create("p", "empty-note", text);
}

function cardNode(name, { hidden = false, selected = false } = {}) {
  const node = create(
    "span",
    `card${hidden ? " hidden-card" : ""}${selected ? " selected" : ""}`,
    hidden ? "？" : name,
  );
  return node;
}

function renderCards(container, cards, { hiddenCount = 0 } = {}) {
  clear(container);
  if (cards) {
    cards.forEach((card) => container.append(cardNode(card)));
    return;
  }
  for (let index = 0; index < hiddenCount; index += 1) {
    container.append(cardNode(null, { hidden: true }));
  }
}

function renderDiscardGroups(container, groups) {
  clear(container);
  if (!groups.length) {
    container.append(emptyNote());
    return;
  }

  groups.forEach((group) => {
    const stack = create("div", "discard-stack");
    stack.style.height = `${43 + Math.max(0, group.length - 1) * 5}px`;
    group.forEach((card, index) => {
      const node = cardNode(card.name, { hidden: card.name === null });
      node.style.left = `${index * 5}px`;
      node.style.top = `${index * 5}px`;
      stack.append(node);
    });
    container.append(stack);
  });
}

function confirmDiscard(card, index, onAction) {
  const dialog = byId("discard-dialog");
  byId("discard-card-name").textContent = card;
  byId("discard-card-effect").textContent =
    CARD_EFFECTS[card] || "このカードには個別の能力説明がありません。";

  byId("discard-cancel-button").onclick = () => dialog.close();
  byId("discard-confirm-button").onclick = () => {
    dialog.close();
    onAction("discard_card", { index });
  };

  if (!dialog.open) {
    dialog.showModal();
  }
}

function confirmAbility(card, label, cardCount, onConfirm) {
  const dialog = byId("ability-dialog");
  byId("ability-dialog-name").textContent = label;
  byId("ability-dialog-card-count").textContent = cardCount;
  byId("ability-dialog-effect").textContent =
    CARD_EFFECTS[card] || "この能力には説明がありません。";

  byId("ability-cancel-button").onclick = () => dialog.close();
  byId("ability-confirm-button").onclick = () => {
    dialog.close();
    onConfirm();
  };

  if (!dialog.open) {
    dialog.showModal();
  }
}

function renderHand(state, onAction) {
  const container = byId("my-hand");
  clear(container);
  const canDiscard = state.available_actions.includes("discard_card");
  const options = canDiscard ? state.interaction?.options || [] : [];

  state.my_hand.forEach((card, index) => {
    if (!canDiscard) {
      container.append(cardNode(card));
      return;
    }
    const option = options.find((item) => item.index === index);
    const button = create("button", "card", card);
    button.type = "button";
    button.title = `${card}を捨てる`;
    button.addEventListener("click", () =>
      confirmDiscard(card, option.index, onAction),
    );
    container.append(button);
  });
}

function actionButton(
  label,
  onClick,
  { kind = "", disabled = false } = {},
) {
  const button = create(
    "button",
    `action-button${kind ? ` ${kind}` : ""}`,
    label,
  );
  button.type = "button";
  button.disabled = disabled;
  button.addEventListener("click", onClick);
  return button;
}

function actionList() {
  return create("div", "action-list");
}

function addAction(list, label, callback, options) {
  list.append(actionButton(label, callback, options));
}

function renderSelectionOptions(
  list,
  options,
  {
    label,
    action,
    payloadKey = "index",
    onAction,
    disabled = () => false,
  },
) {
  options.forEach((option) => {
    addAction(
      list,
      label(option),
      () => onAction(action, { [payloadKey]: option[payloadKey] }),
      {
        kind: option.selected ? "primary" : "secondary",
        disabled: disabled(option),
      },
    );
  });
}

function renderActions(state, handlers) {
  const container = byId("action-content");
  clear(container);
  const actions = new Set(state.available_actions);
  const interaction = state.interaction;
  const step = state.game.turn_step;
  const copy = create(
    "p",
    "action-copy",
    PHASE_MESSAGES[step] || "ゲーム状態を確認してください。",
  );
  const list = actionList();
  container.append(copy, list);

  if (actions.has("declare_esper")) {
    addAction(
      list,
      "✦ ESPERを宣言する",
      () => handlers.action("declare_esper"),
      { kind: "primary" },
    );
  }

  if (actions.has("draw_hand")) {
    addAction(
      list,
      "山札から1枚引く",
      () => handlers.action("draw_hand"),
      { kind: "primary" },
    );
  }

  if (actions.has("open_ability_selection")) {
    addAction(
      list,
      "能力を使う",
      () => handlers.action("open_ability_selection"),
      { kind: "secondary" },
    );
  }
  if (actions.has("pass_turn")) {
    addAction(list, "ターンを終了する", () => handlers.action("pass_turn"));
  }

  if (step === "ABILITY" && interaction) {
    interaction.abilities.forEach((ability) => {
      addAction(
        list,
        `【発動】${ability.label}`,
        () =>
          confirmAbility(
            ability.card,
            ability.label,
            "2枚（同名カード2枚）",
            () =>
              handlers.action("activate_ability", { card: ability.card }),
          ),
        { kind: "secondary", disabled: ability.disabled },
      );
    });
    if (actions.has("open_mimic_selection")) {
      addAction(
        list,
        "【発動】カモフラージュ（擬態）",
        () =>
          confirmAbility(
            "カモフラージュ",
            "カモフラージュ（擬態）",
            "2枚（続けて能力カード1枚を選択）",
            () => handlers.action("open_mimic_selection"),
          ),
        { kind: "secondary" },
      );
    }
    addAction(
      list,
      "手札確認へ戻る",
      () => handlers.action("cancel_ability_selection"),
    );
  }

  if (step === "MIMIC_SELECTION" && interaction) {
    interaction.targets.forEach((target) => {
      addAction(
        list,
        `${target.label}として発動`,
        () =>
          confirmAbility(
            target.card,
            target.label,
            `3枚（カモフラージュ2枚＋${target.card}1枚）`,
            () =>
              handlers.action("activate_mimic", { card: target.card }),
          ),
        { kind: "secondary", disabled: target.disabled },
      );
    });
    addAction(
      list,
      "キャンセル",
      () => handlers.action("cancel_mimic_selection"),
    );
  }

  if (step === "TELEPORT_SELECTION" && interaction) {
    renderSelectionOptions(list, interaction.options, {
      label: (option) => option.label,
      action: "select_teleport_target",
      payloadKey: "card",
      onAction: handlers.action,
    });
  }

  if (step === "PSY_DISCARD_SELECTION" && interaction) {
    renderSelectionOptions(list, interaction.options, {
      label: (option) => option.label,
      action: "select_psychokinesis_discard",
      onAction: handlers.action,
    });
  }

  if (step === "PSY_PUSH_SELECTION" && interaction) {
    renderSelectionOptions(list, interaction.options, {
      label: (option) => option.label,
      action: "select_psychokinesis_push",
      payloadKey: "group_index",
      onAction: handlers.action,
    });
  }

  if (step === "REGEN_SELECTION" && interaction) {
    const count = create(
      "span",
      "selection-count",
      `${interaction.selected_count} / ${interaction.maximum}枚 選択中`,
    );
    list.before(count);
    renderSelectionOptions(list, interaction.options, {
      label: (option) => {
        const owner = option.owner === state.viewer.role ? "自分" : "相手";
        const card = option.name || "裏向き";
        return `${option.selected ? "✓ " : ""}【${owner}】${card}`;
      },
      action: "toggle_healing_selection",
      onAction: handlers.action,
    });
    addAction(
      list,
      "選択を確定する",
      () => handlers.action("confirm_healing"),
      { kind: "primary" },
    );
  }

  if (step === "CLAIR_SELECTION" && interaction) {
    const count = create(
      "span",
      "selection-count",
      `${interaction.selected_count} / ${interaction.maximum}枚 選択中`,
    );
    list.before(count);
    renderSelectionOptions(list, interaction.options, {
      label: (option) => `${option.selected ? "✓ " : ""}${option.label}`,
      action: "toggle_clairvoyance_selection",
      onAction: handlers.action,
    });
    addAction(
      list,
      "選択を確定する",
      () => handlers.action("confirm_clairvoyance"),
      { kind: "primary" },
    );
  }

  if (step === "CLAIR_REVEAL" && interaction) {
    interaction.options.forEach((option) => {
      if (option.selected) {
        const result = create(
          "div",
          "action-button primary",
          `【透視】${option.name}`,
        );
        list.append(result);
      }
    });
    addAction(
      list,
      "確認完了",
      () => handlers.action("finish_clairvoyance"),
      { kind: "primary" },
    );
  }

  if (
    (step === "PRESCIENCE_SELECT_1" ||
      step === "PRESCIENCE_SELECT_2") &&
    interaction
  ) {
    if (interaction.ordered.length) {
      const ordered = create(
        "span",
        "selection-count",
        `決定済み: ${interaction.ordered.join(" → ")}`,
      );
      list.before(ordered);
    }
    renderSelectionOptions(list, interaction.options, {
      label: (option) => option.card,
      action: "select_prescience_card",
      onAction: handlers.action,
    });
  }

  if (state.game.finished) {
    if (state.rematch.requested_by_me) {
      list.append(emptyNote("相手の再戦承認を待っています…"));
    } else {
      addAction(
        list,
        state.rematch.requested_by_opponent
          ? "相手の希望を承認して再戦する"
          : "もう一度対戦する",
        handlers.rematch,
        { kind: "primary" },
      );
    }
    addAction(list, "ルームを退出する", handlers.leave, { kind: "danger" });
  }

  if (step === "ROOM_DISBANDED") {
    addAction(list, "タイトルへ戻る", handlers.returnHome, {
      kind: "primary",
    });
  }

  if (!list.children.length) {
    list.append(
      emptyNote(
        state.game.is_my_turn
          ? "手札または状態が更新されるまでお待ちください。"
          : "相手の操作を待っています…",
      ),
    );
  }
}

function renderLogs(state) {
  byId("latest-log").textContent = state.game.latest_log || "ログはありません";
  const list = byId("log-list");
  clear(list);
  if (!state.logs.length) {
    list.append(emptyNote());
    return;
  }
  [...state.logs].reverse().forEach((log) => {
    const entry = create("div", "log-entry");
    const actor = create(
      "strong",
      "",
      `[${log.time}] ${log.icon} ${log.name}: `,
    );
    entry.append(actor, document.createTextNode(log.text));
    list.append(entry);
  });
}

function renderChat(state) {
  const list = byId("chat-list");
  clear(list);
  if (!state.chat.length) {
    list.append(emptyNote("メッセージはまだありません"));
    return;
  }
  state.chat.forEach((message) => {
    list.append(create("p", "chat-message", message));
  });
  list.scrollTop = list.scrollHeight;
}

function renderPhase(state) {
  const banner = byId("phase-banner");
  const step = state.game.turn_step;
  const prefix =
    state.game.finished
      ? ""
      : state.game.is_my_turn
        ? "あなたのターン — "
        : "相手のターン — ";
  banner.textContent =
    step === "GAME_CLEAR" || step === "GAME_OVER"
      ? state.game.latest_log
      : `${prefix}${PHASE_MESSAGES[step] || ""}`;
  banner.className = `phase-banner${
    state.game.finished
      ? " finished"
      : state.game.is_my_turn
        ? " attention"
        : ""
  }`;
}

export function renderGame(state, handlers) {
  const discardDialog = byId("discard-dialog");
  if (
    discardDialog.open &&
    !state.available_actions.includes("discard_card")
  ) {
    discardDialog.close();
  }
  const abilityDialog = byId("ability-dialog");
  if (
    abilityDialog.open &&
    !["ABILITY", "MIMIC_SELECTION"].includes(state.game.turn_step)
  ) {
    abilityDialog.close();
  }
  byId("room-player").textContent =
    `${state.viewer.name} / プレイヤー${state.viewer.role === "p1" ? "1" : "2"}`;
  byId("room-code").textContent = state.room_id;
  byId("opponent-name").textContent = state.opponent.name;
  byId("opponent-count").textContent = state.opponent.hand_count;
  byId("deck-count").textContent = state.game.deck_count;
  byId("deck-count-center").textContent = state.game.deck_count;

  renderPhase(state);
  renderCards(byId("opponent-hand"), state.opponent.hand, {
    hiddenCount: state.opponent.hand_count,
  });
  renderCards(byId("excluded-cards"), state.excluded_cards.map((card) => card), {
    hiddenCount: 0,
  });
  [...byId("excluded-cards").children].forEach((node, index) => {
    if (state.excluded_cards[index] === null) {
      node.textContent = "？";
      node.classList.add("hidden-card");
    }
  });
  renderDiscardGroups(byId("opponent-discards"), state.discards.opponent);
  renderDiscardGroups(byId("my-discards"), state.discards.mine);
  renderHand(state, handlers.action);

  byId("hand-guide").textContent = state.available_actions.includes(
    "discard_card",
  )
    ? "捨てるカードを選択"
    : `${state.my_hand.length}枚`;

  renderActions(state, handlers);
  renderLogs(state);
  renderChat(state);
}

export function setConnectionStatus(connected) {
  const node = byId("connection-status");
  node.classList.toggle("offline", !connected);
  node.lastChild.textContent = connected ? " 接続中" : " 再接続中";
}
