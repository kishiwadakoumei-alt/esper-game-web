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
  PRESCIENCE_SELECT_1: "3枚を上から戻す順番に選んでください。",
  PRESCIENCE_SELECT_2: "3枚を上から戻す順番に選んでください。",
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

let prescienceOrder = [];
let psychokinesisSelection = null;
let lastActionEventId = null;
let lastTurnOwner = null;
let lastTurnNotificationStep = null;
let activeNotification = null;
let notificationTimer = null;
let notificationGapTimer = null;
const notificationQueue = [];
let previousHandCounts = null;
let handTrackingContext = null;
let previousTurnStep = null;
const newlyDrawnCards = new Map();
const NEW_CARD_HOLD_MS = 3000;
const NEW_CARD_FADE_MS = 400;
const NEW_CARD_HIGHLIGHT_MS = NEW_CARD_HOLD_MS + NEW_CARD_FADE_MS;

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

function cardNode(
  name,
  { hidden = false, selected = false, newlyDrawnElapsed = null } = {},
) {
  const node = create(
    "span",
    `card${hidden ? " hidden-card" : ""}${selected ? " selected" : ""}${
      newlyDrawnElapsed === null ? "" : " newly-drawn"
    }`,
    hidden ? "？" : name,
  );
  if (newlyDrawnElapsed !== null) {
    node.style.animationDelay = `-${newlyDrawnElapsed}ms`;
  }
  return node;
}

function renderCards(
  container,
  cards,
  { hiddenCount = 0, selectedIndices = new Set() } = {},
) {
  clear(container);
  if (cards) {
    cards.forEach((card, index) =>
      container.append(
        cardNode(card, { selected: selectedIndices.has(index) }),
      ),
    );
    return;
  }
  for (let index = 0; index < hiddenCount; index += 1) {
    container.append(
      cardNode(null, {
        hidden: true,
        selected: selectedIndices.has(index),
      }),
    );
  }
}

function renderDiscardGroups(
  container,
  groups,
  selectedGroups = new Set(),
  selectedCards = new Set(),
) {
  clear(container);
  if (!groups.length) {
    container.append(emptyNote());
    return;
  }

  groups.forEach((group, groupIndex) => {
    const stack = create("div", "discard-stack");
    const selectedGroup = selectedGroups.has(groupIndex);
    stack.style.height = `${43 + Math.max(0, group.length - 1) * 5}px`;
    group.forEach((card, index) => {
      const selected =
        selectedGroup || selectedCards.has(`${groupIndex}:${index}`);
      const node = cardNode(card.name, {
        hidden: !card.is_face_up,
        selected,
      });
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

function showDiscardReveal(card) {
  const dialog = byId("discard-reveal-dialog");
  byId("discard-reveal-name").textContent = card;
  byId("discard-reveal-effect").textContent =
    CARD_EFFECTS[card] || "このカードには個別の能力説明がありません。";
  byId("discard-reveal-close-button").onclick = () => dialog.close();
  if (!dialog.open) {
    dialog.showModal();
  }
}

function confirmAbility(card, label, cardCount, onConfirm, onCancel) {
  const dialog = byId("ability-dialog");
  byId("ability-dialog-name").textContent = label;
  byId("ability-dialog-card-count").textContent = cardCount;
  byId("ability-dialog-effect").textContent =
    CARD_EFFECTS[card] || "この能力には説明がありません。";

  const cancel = () => {
    dialog.close();
    if (onCancel) {
      onCancel();
    }
  };
  byId("ability-cancel-button").onclick = cancel;
  dialog.oncancel = (event) => {
    event.preventDefault();
    cancel();
  };
  byId("ability-confirm-button").onclick = () => {
    dialog.close();
    onConfirm();
  };

  if (!dialog.open) {
    dialog.showModal();
  }
}

function confirmTeleportTarget(card, label, onConfirm, onCancel) {
  const dialog = byId("teleport-dialog");
  byId("teleport-target-name").textContent = label;
  byId("teleport-target-effect").textContent =
    CARD_EFFECTS[card] || "この能力には説明がありません。";

  const cancel = () => {
    dialog.close();
    if (onCancel) {
      onCancel();
    }
  };
  byId("teleport-cancel-button").onclick = cancel;
  dialog.oncancel = (event) => {
    event.preventDefault();
    cancel();
  };
  byId("teleport-confirm-button").onclick = () => {
    dialog.close();
    onConfirm();
  };

  if (!dialog.open) {
    dialog.showModal();
  }
}

function confirmPsychokinesisTarget(
  state,
  option,
  handlers,
  mode,
) {
  const dialog = byId("psychokinesis-dialog");
  const isDiscard = mode === "discard";
  psychokinesisSelection = isDiscard
    ? { mode, index: option.index }
    : { mode, groupIndex: option.group_index };
  renderGame(state, handlers);

  byId("psychokinesis-dialog-kicker").textContent = isDiscard
    ? "CONFIRM PSYCHOKINESIS DISCARD"
    : "CONFIRM PSYCHOKINESIS RETURN";
  byId("psychokinesis-dialog-title").textContent = isDiscard
    ? "この手札を捨てさせますか？"
    : "この捨て札を手札へ戻しますか？";
  byId("psychokinesis-target-label").textContent = option.label;
  byId("psychokinesis-target-effect").textContent = isDiscard
    ? "相手の手札から選んだ1枚を表向きで捨てさせます。"
    : "選んだ裏向きの捨て札1枚を相手の手札へ戻します。";
  byId("psychokinesis-confirm-button").textContent = isDiscard
    ? "捨てさせる"
    : "戻す";

  const cancelSelection = () => {
    if (dialog.open) {
      dialog.close();
    }
    psychokinesisSelection = null;
    renderGame(state, handlers);
  };
  byId("psychokinesis-cancel-button").onclick = cancelSelection;
  dialog.oncancel = (event) => {
    event.preventDefault();
    cancelSelection();
  };
  byId("psychokinesis-confirm-button").onclick = () => {
    dialog.close();
    psychokinesisSelection = null;
    renderGame(state, handlers);
    handlers.action(
      isDiscard
        ? "select_psychokinesis_discard"
        : "select_psychokinesis_push",
      isDiscard
        ? { index: option.index }
        : { group_index: option.group_index },
    );
  };

  if (!dialog.open) {
    dialog.showModal();
  }
}

function countCards(cards) {
  return cards.reduce((counts, card) => {
    counts.set(card, (counts.get(card) || 0) + 1);
    return counts;
  }, new Map());
}

function resetHandTracking(state) {
  previousHandCounts = countCards(state.my_hand);
  handTrackingContext = `${state.room_id}:${state.viewer.role}`;
  previousTurnStep = state.game.turn_step;
  newlyDrawnCards.clear();
}

function updateNewlyDrawnCards(state) {
  const context = `${state.room_id}:${state.viewer.role}`;
  const restarted =
    ["GAME_CLEAR", "GAME_OVER"].includes(previousTurnStep) &&
    !["GAME_CLEAR", "GAME_OVER"].includes(state.game.turn_step);
  if (
    previousHandCounts === null ||
    handTrackingContext !== context ||
    restarted
  ) {
    resetHandTracking(state);
    return;
  }

  const now = performance.now();
  const currentCounts = countCards(state.my_hand);
  currentCounts.forEach((count, card) => {
    const previousCount = previousHandCounts.get(card) || 0;
    for (let occurrence = previousCount; occurrence < count; occurrence += 1) {
      newlyDrawnCards.set(`${card}:${occurrence}`, now);
    }
  });
  [...newlyDrawnCards].forEach(([key, startedAt]) => {
    if (now - startedAt >= NEW_CARD_HIGHLIGHT_MS) {
      newlyDrawnCards.delete(key);
    }
  });
  previousHandCounts = currentCounts;
  previousTurnStep = state.game.turn_step;
}

export function resetRenderState() {
  previousHandCounts = null;
  handTrackingContext = null;
  previousTurnStep = null;
  newlyDrawnCards.clear();
  psychokinesisSelection = null;
  lastActionEventId = null;
  lastTurnOwner = null;
  lastTurnNotificationStep = null;
  notificationQueue.length = 0;
  activeNotification = null;
  window.clearTimeout(notificationTimer);
  window.clearTimeout(notificationGapTimer);
  const actionOverlay = byId("action-event-overlay");
  const extraTurnOverlay = byId("extra-turn-overlay");
  ["choice-dialog", "discard-reveal-dialog"].forEach((id) => {
    const dialog = byId(id);
    if (dialog?.open) {
      dialog.close();
    }
  });
  if (actionOverlay) {
    actionOverlay.hidden = true;
  }
  if (extraTurnOverlay) {
    extraTurnOverlay.hidden = true;
  }
}

function renderHand(state, onAction) {
  const container = byId("my-hand");
  clear(container);
  const canDiscard = state.available_actions.includes("discard_card");
  const options = canDiscard ? state.interaction?.options || [] : [];
  const occurrences = new Map();
  const now = performance.now();

  state.my_hand.forEach((card, index) => {
    const occurrence = occurrences.get(card) || 0;
    occurrences.set(card, occurrence + 1);
    const startedAt = newlyDrawnCards.get(`${card}:${occurrence}`);
    const newlyDrawnElapsed =
      startedAt === undefined
        ? null
        : Math.min(now - startedAt, NEW_CARD_HIGHLIGHT_MS);
    if (!canDiscard) {
      container.append(cardNode(card, { newlyDrawnElapsed }));
      return;
    }
    const option = options.find((item) => item.index === index);
    const button = create(
      "button",
      `card${newlyDrawnElapsed === null ? "" : " newly-drawn"}`,
      card,
    );
    if (newlyDrawnElapsed !== null) {
      button.style.animationDelay = `-${newlyDrawnElapsed}ms`;
    }
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

function showPrescienceConfirmation(state, handlers) {
  const dialog = byId("prescience-dialog");
  const orderList = byId("prescience-order-list");
  const options = state.interaction.options;
  clear(orderList);

  prescienceOrder.forEach((optionIndex, position) => {
    const option = options.find((item) => item.index === optionIndex);
    const item = create("li");
    item.append(
      create("span", "", `上から${position + 1}枚目：`),
      create("strong", "", option.card),
    );
    orderList.append(item);
  });

  byId("prescience-back-button").onclick = () => {
    dialog.close();
    prescienceOrder.pop();
    renderActions(state, handlers);
  };
  byId("prescience-confirm-button").onclick = () => {
    const order = [...prescienceOrder];
    dialog.close();
    prescienceOrder = [];
    handlers.action("confirm_prescience_order", { order });
  };

  if (!dialog.open) {
    dialog.showModal();
  }
}

function renderPrescienceSelection(list, state, handlers) {
  const options = state.interaction.options;
  const validIndices = new Set(options.map((option) => option.index));
  prescienceOrder = prescienceOrder.filter((index) => validIndices.has(index));

  options.forEach((option) => {
    const position = prescienceOrder.indexOf(option.index);
    const button = create(
      "button",
      `prescience-option${position >= 0 ? " selected" : ""}`,
    );
    button.type = "button";
    button.append(
      create("span", "", option.card),
      create(
        "strong",
        "prescience-position",
        position >= 0 ? `上から${position + 1}枚目` : "",
      ),
    );
    button.addEventListener("click", () => {
      const selectedPosition = prescienceOrder.indexOf(option.index);
      if (selectedPosition >= 0) {
        prescienceOrder.splice(selectedPosition, 1);
      } else if (prescienceOrder.length < options.length) {
        prescienceOrder.push(option.index);
      }
      const completed = prescienceOrder.length === options.length;
      if (completed) {
        closeChoiceDialog();
        showPrescienceConfirmation(state, handlers);
      } else {
        renderActions(state, handlers);
      }
    });
    list.append(button);
  });

  if (prescienceOrder.length === options.length) {
    addAction(
      list,
      "選択内容を確認する",
      () => showPrescienceConfirmation(state, handlers),
      { kind: "primary" },
    );
  }
}

function closeChoiceDialog() {
  const dialog = byId("choice-dialog");
  if (dialog.open) {
    dialog.close();
  }
}

function choiceDialogIsBlocked() {
  return [
    "ability-dialog",
    "teleport-dialog",
    "prescience-dialog",
    "psychokinesis-dialog",
    "discard-dialog",
    "discard-reveal-dialog",
  ].some((id) => byId(id).open);
}

function openChoiceDialog({ kicker, title, copy, onBack = null }) {
  if (choiceDialogIsBlocked()) {
    closeChoiceDialog();
    return null;
  }
  const dialog = byId("choice-dialog");
  const options = byId("choice-dialog-options");
  const back = byId("choice-dialog-back-button");
  clear(options);
  byId("choice-dialog-kicker").textContent = kicker;
  byId("choice-dialog-title").textContent = title;
  byId("choice-dialog-copy").textContent = copy;
  back.parentElement.hidden = !onBack;
  back.onclick = () => {
    dialog.close();
    onBack();
  };
  dialog.oncancel = (event) => {
    event.preventDefault();
    if (onBack) {
      dialog.close();
      onBack();
    }
  };
  if (!dialog.open) {
    dialog.showModal();
  }
  return options;
}

function renderChoiceDialog(state, handlers) {
  const actions = new Set(state.available_actions);
  const interaction = state.interaction;
  const step = state.game.turn_step;
  const modalStep = [
    "ABILITY",
    "MIMIC_SELECTION",
    "TELEPORT_SELECTION",
    "CLAIR_REVEAL",
    "PRESCIENCE_SELECT_1",
    "PRESCIENCE_SELECT_2",
    "ROOM_DISBANDED",
  ].includes(step) || state.game.finished;

  if (!modalStep) {
    closeChoiceDialog();
    return;
  }

  if (step === "ABILITY" && interaction) {
    const options = openChoiceDialog({
      kicker: "CHOOSE PSYCHIC ABILITY",
      title: "発動する能力を選択",
      copy: PHASE_MESSAGES[step],
      onBack: () => handlers.action("cancel_ability_selection"),
    });
    if (!options) {
      return;
    }
    interaction.abilities.forEach((ability) => {
      addAction(
        options,
        `【発動】${ability.label}`,
        () => {
          closeChoiceDialog();
          confirmAbility(
            ability.card,
            ability.label,
            "2枚（同名カード2枚）",
            () => handlers.action("activate_ability", { card: ability.card }),
            () => renderActions(state, handlers),
          );
        },
        { kind: "secondary", disabled: ability.disabled },
      );
    });
    if (actions.has("open_mimic_selection")) {
      addAction(
        options,
        "【発動】カモフラージュ（擬態）",
        () => {
          closeChoiceDialog();
          confirmAbility(
            "カモフラージュ",
            "カモフラージュ（擬態）",
            "2枚（続けて能力カード1枚を選択）",
            () => handlers.action("open_mimic_selection"),
            () => renderActions(state, handlers),
          );
        },
        { kind: "secondary" },
      );
    }
    return;
  }

  if (step === "MIMIC_SELECTION" && interaction) {
    const options = openChoiceDialog({
      kicker: "CHOOSE MIMIC TARGET",
      title: "擬態する能力を選択",
      copy: PHASE_MESSAGES[step],
      onBack: () => handlers.action("cancel_mimic_selection"),
    });
    if (!options) {
      return;
    }
    interaction.targets.forEach((target) => {
      addAction(
        options,
        `${target.label}として発動`,
        () => {
          closeChoiceDialog();
          confirmAbility(
            target.card,
            target.label,
            `3枚（カモフラージュ2枚＋${target.card}1枚）`,
            () => handlers.action("activate_mimic", { card: target.card }),
            () => renderActions(state, handlers),
          );
        },
        { kind: "secondary", disabled: target.disabled },
      );
    });
    return;
  }

  if (step === "TELEPORT_SELECTION" && interaction) {
    const options = openChoiceDialog({
      kicker: "CHOOSE TELEPORT TARGET",
      title: "捨てさせる能力を選択",
      copy: PHASE_MESSAGES[step],
    });
    if (!options) {
      return;
    }
    interaction.options.forEach((option) => {
      addAction(
        options,
        option.label,
        () => {
          closeChoiceDialog();
          confirmTeleportTarget(
            option.card,
            option.label,
            () => handlers.action("select_teleport_target", {
              card: option.card,
            }),
            () => renderActions(state, handlers),
          );
        },
        { kind: "secondary" },
      );
    });
    return;
  }

  if (
    ["PRESCIENCE_SELECT_1", "PRESCIENCE_SELECT_2"].includes(step) &&
    interaction
  ) {
    const options = openChoiceDialog({
      kicker: "ORDER THE FUTURE",
      title: "山札へ戻す順番を選択",
      copy: PHASE_MESSAGES[step],
    });
    if (options) {
      renderPrescienceSelection(options, state, handlers);
    }
    return;
  }

  if (step === "CLAIR_REVEAL" && interaction) {
    const options = openChoiceDialog({
      kicker: "CLAIRVOYANCE RESULT",
      title: "透視結果",
      copy: PHASE_MESSAGES[step],
    });
    if (!options) {
      return;
    }
    interaction.options.forEach((option) => {
      if (option.selected) {
        options.append(create(
          "div",
          "action-button primary",
          `【透視】${option.name}`,
        ));
      }
    });
    addAction(
      options,
      "確認完了",
      () => {
        closeChoiceDialog();
        handlers.action("finish_clairvoyance");
      },
      { kind: "primary" },
    );
    return;
  }

  if (state.game.finished) {
    const options = openChoiceDialog({
      kicker: "GAME RESULT",
      title: "対戦結果",
      copy: state.game.latest_log,
    });
    if (!options) {
      return;
    }
    if (state.rematch.requested_by_me) {
      options.append(emptyNote("相手の再戦承認を待っています…"));
    } else {
      addAction(
        options,
        state.rematch.requested_by_opponent
          ? "相手の希望を承認して再戦する"
          : "もう一度対戦する",
        () => {
          closeChoiceDialog();
          handlers.rematch();
        },
        { kind: "primary" },
      );
    }
    addAction(options, "ルームを退出する", handlers.leave, {
      kind: "danger",
    });
    return;
  }

  if (step === "ROOM_DISBANDED") {
    const options = openChoiceDialog({
      kicker: "ROOM CLOSED",
      title: "ルームが解散されました",
      copy: PHASE_MESSAGES[step],
    });
    if (options) {
      addAction(options, "タイトルへ戻る", handlers.returnHome, {
        kind: "primary",
      });
    }
  }
}

function renderActionBar(state, handlers) {
  const bar = byId("context-action-bar");
  const copy = byId("context-action-copy");
  const buttons = byId("context-action-buttons");
  const actions = new Set(state.available_actions);
  const interaction = state.interaction;
  const step = state.game.turn_step;
  clear(buttons);
  let message = "";

  if (actions.has("declare_esper")) {
    addAction(
      buttons,
      "✦ ESPERを宣言する",
      () => handlers.action("declare_esper"),
      { kind: "primary" },
    );
  }

  if (step === "THINK") {
    message = "次の行動を選択してください。";
    if (actions.has("open_ability_selection")) {
      addAction(
        buttons,
        "能力を使う",
        () => handlers.action("open_ability_selection"),
        { kind: "secondary" },
      );
    }
    if (actions.has("pass_turn")) {
      addAction(
        buttons,
        "ターンを終了する",
        () => handlers.action("pass_turn"),
      );
    }
  } else if (step === "REGEN_SELECTION" && interaction) {
    message = `盤面から山札へ戻すカードを選択してください（${interaction.selected_count} / ${interaction.maximum}枚）`;
    addAction(
      buttons,
      "選択を確定する",
      () => handlers.action("confirm_healing"),
      { kind: "primary" },
    );
  } else if (step === "CLAIR_SELECTION" && interaction) {
    message = `相手の盤面から透視するカードを選択してください（${interaction.selected_count} / ${interaction.maximum}枚）`;
    addAction(
      buttons,
      "選択を確定する",
      () => handlers.action("confirm_clairvoyance"),
      { kind: "primary" },
    );
  }

  const visible = Boolean(message || buttons.children.length);
  copy.textContent = message;
  bar.hidden = !visible;
  byId("game-screen").classList.toggle("has-context-actions", visible);
}

function renderActions(state, handlers) {
  renderActionBar(state, handlers);
  renderChoiceDialog(state, handlers);
}

function renderLogs(state) {
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

function extraTurnLevel(count) {
  return Math.min(Math.max(count, 1), 4);
}

function finishNotification(overlay) {
  overlay.classList.add("leaving");
  notificationTimer = window.setTimeout(() => {
    overlay.hidden = true;
    overlay.classList.remove("leaving");
    activeNotification = null;
    notificationGapTimer = window.setTimeout(showNextNotification, 200);
  }, 250);
}

function showNextNotification() {
  if (activeNotification || !notificationQueue.length) {
    return;
  }
  activeNotification = notificationQueue.shift();
  const isTimeLeap = activeNotification.kind === "time_leap";
  const overlay = byId(
    isTimeLeap ? "extra-turn-overlay" : "action-event-overlay",
  );

  if (isTimeLeap) {
    const levelClass =
      `extra-turn-level-${extraTurnLevel(activeNotification.level)}`;
    overlay.className = `extra-turn-overlay ${levelClass}`;
    byId("extra-turn-overlay-title").textContent = activeNotification.title;
    byId("extra-turn-overlay-count").textContent = activeNotification.detail;
  } else {
    overlay.className =
      `action-event-overlay tone-${activeNotification.tone || "ability"}`;
    byId("action-event-kicker").textContent =
      activeNotification.kind === "turn_change"
        ? "TURN CHANGE"
        : activeNotification.tone === "impact"
          ? "YOUR CARDS CHANGED"
          : "OPPONENT ACTION";
    byId("action-event-title").textContent = activeNotification.title;
    byId("action-event-detail").textContent = activeNotification.detail;
  }

  overlay.hidden = false;
  notificationTimer = window.setTimeout(
    () => finishNotification(overlay),
    activeNotification.duration_ms || 2000,
  );
}

function enqueueNotification(notification, { priority = false } = {}) {
  if (priority) {
    notificationQueue.unshift(notification);
  } else {
    notificationQueue.push(notification);
  }
  showNextNotification();
}

function renderActionEvents(state, { suppress = false } = {}) {
  const events = state.action_events || [];
  const newestId = events.reduce(
    (maximum, event) => Math.max(maximum, event.id),
    0,
  );
  if (lastActionEventId === null || suppress) {
    lastActionEventId = newestId;
    return;
  }

  events
    .filter((event) => event.id > lastActionEventId)
    .sort((left, right) => left.id - right.id)
    .forEach((event) => {
      const isTimeLeap = event.kind === "time_leap";
      if (isTimeLeap || event.actor_role !== state.viewer.role) {
        enqueueNotification(
          {
            ...event,
            level: state.game.extra_turn_chain || 1,
          },
          { priority: isTimeLeap },
        );
      }
    });
  lastActionEventId = Math.max(lastActionEventId, newestId);
}

function renderTurnChange(state, { suppress = false } = {}) {
  const currentOwner = state.game.current_turn;
  const currentStep = state.game.turn_step;
  const turnIsActive = ![
    "WAITING",
    "DECIDING_TURN",
    "GAME_CLEAR",
    "GAME_OVER",
    "ROOM_DISBANDED",
  ].includes(currentStep);
  const startsAfterDecision = ["WAITING", "DECIDING_TURN"].includes(
    lastTurnNotificationStep,
  );
  const shouldNotify =
    lastTurnOwner !== null &&
    !suppress &&
    turnIsActive &&
    (currentOwner !== lastTurnOwner || startsAfterDecision);

  lastTurnOwner = currentOwner;
  lastTurnNotificationStep = currentStep;
  if (!shouldNotify) {
    return;
  }

  const isMyTurn = currentOwner === state.viewer.role;
  enqueueNotification({
    kind: "turn_change",
    tone: isMyTurn ? "turn-mine" : "turn-opponent",
    title: isMyTurn ? "あなたの番です" : "相手の番です",
    detail: "",
    duration_ms: 2000,
  });
}

function renderExtraTurnIndicators(state) {
  const count = state.game.extra_turn_chain || 0;
  const badge = byId("extra-turn-badge");

  if (count === 0) {
    badge.hidden = true;
    return;
  }

  const levelClass = `extra-turn-level-${extraTurnLevel(count)}`;
  badge.hidden = false;
  badge.className = `extra-turn-badge ${levelClass}`;
  badge.textContent = `EXTRA TURN ×${count}`;
}

function renderPhase(state) {
  const banner = byId("phase-banner");
  const step = state.game.turn_step;
  const extraTurnCount = state.game.extra_turn_chain || 0;
  if (extraTurnCount > 0 && !state.game.finished) {
    const owner = state.game.is_my_turn
      ? `タイムリープによる${extraTurnCount}回目の追加ターン`
      : `相手のタイムリープ追加ターン（${extraTurnCount}回目）`;
    banner.textContent = `${owner} — ${PHASE_MESSAGES[step] || ""}`;
    banner.className =
      `phase-banner extra-turn extra-turn-level-${
        extraTurnLevel(extraTurnCount)
      }`;
    return;
  }

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

function psychokinesisHighlights(state) {
  const highlights = {
    hand: new Set(),
    discards: new Set(),
  };
  const interaction = state.interaction;
  if (!interaction || !psychokinesisSelection) {
    return highlights;
  }
  if (
    interaction.kind === "psychokinesis_discard" &&
    psychokinesisSelection.mode === "discard"
  ) {
    highlights.hand.add(psychokinesisSelection.index);
  } else if (
    interaction.kind === "psychokinesis_push" &&
    psychokinesisSelection.mode === "push"
  ) {
    highlights.discards.add(psychokinesisSelection.groupIndex);
  }
  return highlights;
}

function makeBoardTargetClickable(
  node,
  onSelect,
  label,
  className = "selectable-target",
) {
  if (!node) {
    return;
  }
  node.classList.add(className);
  node.tabIndex = 0;
  node.setAttribute("role", "button");
  node.setAttribute("aria-label", label);
  node.addEventListener("click", onSelect);
  node.addEventListener("keydown", (event) => {
    if (["Enter", " "].includes(event.key)) {
      event.preventDefault();
      onSelect();
    }
  });
}

function bindPsychokinesisBoardTargets(state, handlers) {
  const interaction = state.interaction;
  if (!interaction) {
    return;
  }
  if (interaction.kind === "psychokinesis_discard") {
    const handCards = byId("opponent-hand").children;
    interaction.options.forEach((option) => {
      makeBoardTargetClickable(
        handCards[option.index],
        () => confirmPsychokinesisTarget(state, option, handlers, "discard"),
        `${option.label}を捨てさせる`,
      );
    });
  } else if (interaction.kind === "psychokinesis_push") {
    const discardGroups = byId("opponent-discards").children;
    interaction.options.forEach((option) => {
      makeBoardTargetClickable(
        discardGroups[option.group_index],
        () => confirmPsychokinesisTarget(state, option, handlers, "push"),
        `${option.label}を手札へ戻す`,
      );
    });
  }
}

function bindHealingBoardTargets(state, handlers) {
  const interaction = state.interaction;
  if (!interaction || interaction.kind !== "healing") {
    return;
  }
  interaction.options.forEach((option) => {
    if (!option.target) {
      return;
    }
    const container = byId(
      option.target.zone === "mine" ? "my-discards" : "opponent-discards",
    );
    const stack = container.children[option.target.group_index];
    const card = stack?.children[option.target.item_index];
    const owner = option.target.zone === "mine" ? "自分" : "相手";
    const cardLabel = option.name || "裏向きのカード";
    makeBoardTargetClickable(
      card,
      () => handlers.action("toggle_healing_selection", {
        index: option.index,
      }),
      `${owner}の${cardLabel}を選択`,
    );
  });
}

function bindClairvoyanceBoardTargets(state, handlers) {
  const interaction = state.interaction;
  if (!interaction || interaction.kind !== "clairvoyance") {
    return;
  }
  interaction.options.forEach((option) => {
    if (!option.target) {
      return;
    }
    const node = option.target.zone === "opponent_hand"
      ? byId("opponent-hand").children[option.target.index]
      : byId("opponent-discards").children[option.target.index];
    makeBoardTargetClickable(
      node,
      () => handlers.action("toggle_clairvoyance_selection", {
        index: option.index,
      }),
      `${option.label}を透視対象に選択`,
    );
  });
}

function bindOwnDiscardReveal(state) {
  if (state.game.turn_step === "REGEN_SELECTION") {
    return;
  }
  const container = byId("my-discards");
  state.discards.mine.forEach((group, groupIndex) => {
    group.forEach((card, itemIndex) => {
      if (card.is_face_up || !card.name) {
        return;
      }
      const node = container.children[groupIndex]?.children[itemIndex];
      makeBoardTargetClickable(
        node,
        () => showDiscardReveal(card.name),
        "裏向きの捨て札の内容を見る",
        "revealable-card",
      );
    });
  });
}

function bindBoardInteractions(state, handlers) {
  bindPsychokinesisBoardTargets(state, handlers);
  bindHealingBoardTargets(state, handlers);
  bindClairvoyanceBoardTargets(state, handlers);
  bindOwnDiscardReveal(state);
}

function bindDeckAction(state, handlers) {
  const deck = byId("deck-action-button");
  const canDraw = state.available_actions.includes("draw_hand");
  deck.disabled = !canDraw;
  deck.classList.toggle("actionable", canDraw);
  deck.setAttribute("aria-label", canDraw ? "山札から1枚引く" : "山札");
  deck.onclick = canDraw
    ? () => handlers.action("draw_hand")
    : null;
}

function healingHighlights(state) {
  const highlights = {
    mine: new Set(),
    opponent: new Set(),
  };
  const interaction = state.interaction;
  if (!interaction || interaction.kind !== "healing") {
    return highlights;
  }

  interaction.options
    .filter((option) => option.selected && option.target)
    .forEach((option) => {
      const key = `${option.target.group_index}:${option.target.item_index}`;
      highlights[option.target.zone].add(key);
    });
  return highlights;
}

function clairvoyanceHighlights(state) {
  const highlights = {
    hand: new Set(),
    discards: new Set(),
  };
  const interaction = state.interaction;
  if (
    !interaction ||
    !["clairvoyance", "clairvoyance_reveal"].includes(interaction.kind)
  ) {
    return highlights;
  }

  interaction.options
    .filter((option) => option.selected && option.target)
    .forEach((option) => {
      if (option.target.zone === "opponent_hand") {
        highlights.hand.add(option.target.index);
      } else if (option.target.zone === "opponent_discard") {
        highlights.discards.add(option.target.index);
      }
    });
  return highlights;
}

export function renderGame(
  state,
  handlers,
  { suppressActionEvents = false } = {},
) {
  updateNewlyDrawnCards(state);
  renderActionEvents(state, { suppress: suppressActionEvents });
  renderTurnChange(state, { suppress: suppressActionEvents });
  const revealDialog = byId("discard-reveal-dialog");
  if (revealDialog.open) {
    revealDialog.close();
  }
  const discardDialog = byId("discard-dialog");
  if (
    discardDialog.open &&
    !state.available_actions.includes("discard_card")
  ) {
    discardDialog.close();
  }
  if (
    !["PRESCIENCE_SELECT_1", "PRESCIENCE_SELECT_2"].includes(
      state.game.turn_step,
    )
  ) {
    prescienceOrder = [];
    const prescienceDialog = byId("prescience-dialog");
    if (prescienceDialog.open) {
      prescienceDialog.close();
    }
  }
  const teleportDialog = byId("teleport-dialog");
  if (
    teleportDialog.open &&
    state.game.turn_step !== "TELEPORT_SELECTION"
  ) {
    teleportDialog.close();
  }
  const abilityDialog = byId("ability-dialog");
  if (
    abilityDialog.open &&
    !["ABILITY", "MIMIC_SELECTION"].includes(state.game.turn_step)
  ) {
    abilityDialog.close();
  }
  const psychokinesisDialog = byId("psychokinesis-dialog");
  if (
    !["PSY_DISCARD_SELECTION", "PSY_PUSH_SELECTION"].includes(
      state.game.turn_step,
    )
  ) {
    psychokinesisSelection = null;
    if (psychokinesisDialog.open) {
      psychokinesisDialog.close();
    }
  }
  byId("room-player").textContent =
    `${state.viewer.name} / プレイヤー${state.viewer.role === "p1" ? "1" : "2"}`;
  byId("room-code").textContent = state.room_id;
  byId("opponent-name").textContent = state.opponent.name;
  byId("opponent-count").textContent = state.opponent.hand_count;
  byId("deck-count").textContent = state.game.deck_count;
  byId("deck-count-center").textContent = state.game.deck_count;

  renderExtraTurnIndicators(state);
  renderPhase(state);
  const clairHighlights = clairvoyanceHighlights(state);
  const psychHighlights = psychokinesisHighlights(state);
  const regenHighlights = healingHighlights(state);
  const opponentHandHighlights = new Set([
    ...clairHighlights.hand,
    ...psychHighlights.hand,
  ]);
  renderCards(byId("opponent-hand"), state.opponent.hand, {
    hiddenCount: state.opponent.hand_count,
    selectedIndices: opponentHandHighlights,
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
  renderDiscardGroups(
    byId("opponent-discards"),
    state.discards.opponent,
    new Set([
      ...clairHighlights.discards,
      ...psychHighlights.discards,
    ]),
    regenHighlights.opponent,
  );
  renderDiscardGroups(
    byId("my-discards"),
    state.discards.mine,
    new Set(),
    regenHighlights.mine,
  );
  renderHand(state, handlers.action);
  bindBoardInteractions(state, handlers);
  bindDeckAction(state, handlers);

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
