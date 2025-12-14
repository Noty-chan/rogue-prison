/* app.js — фронт: рендер экранов + перетаскивание карт.
   Важная идея: сервер — источник истины. Фронт только показывает state и отправляет actions.
*/
let SID = null;
let STATE = null;
let CONTENT = null; // /api/content
let CARD_INDEX = new Map(); // id -> {base, up}
let MAP_ZOOM = 1;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function show(el, yes=true){ el.classList.toggle('hidden', !yes); }
function toast(msg){
  const t = $('#toast');
  if(!msg){ show(t,false); return; }
  t.textContent = msg;
  show(t,true);
  requestAnimationFrame(()=>{ t.classList.add('show'); });
  setTimeout(()=>{ t.classList.remove('show'); }, 1600);
  setTimeout(()=>{ show(t,false); }, 1800);
}

async function api(path, body){
  const res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body || {})
  });
  return await res.json();
}

async function apiGet(path){
  const res = await fetch(path);
  return await res.json();
}

async function bootstrap(){
  const saved = localStorage.getItem('mprl_sid');
  const data = await api('/api/bootstrap', {sid: saved || null});
  SID = data.sid;
  localStorage.setItem('mprl_sid', SID);
  STATE = data.state;
  renderAll();
  if(STATE?.run){
    await dispatch({type:'CONTINUE'});
  }
  // подгрузим контент для кодекса/наследия
  try{
    CONTENT = await apiGet('/api/content');
    CARD_INDEX = new Map();
    for(const item of CONTENT.cards){
      CARD_INDEX.set(item.base.id, item);
    }
  }catch(e){
    // ok
  }
}

async function dispatch(action){
  const data = await api('/api/action', {sid: SID, action});
  STATE = data.state;
  renderAll();
  if(STATE?.ui?.toast) toast(STATE.ui.toast);
}

// --- helpers ---
function cardDefFromId(id, up=false){
  const item = CARD_INDEX.get(id);
  if(!item) return null;
  return up ? item.up : item.base;
}
function rarityName(r){
  return ({common:'Обычная',uncommon:'Необычная',rare:'Редкая',legendary:'Легендарная'})[r] || r;
}
function typeName(t){
  return ({attack:'Атака',defense:'Защита',skill:'Навык',upgrade:'Апгрейд'})[t] || t;
}
function tagToRu(tag){
  const map = {
    charge:'заряд', poison:'яд', burn:'ожог', bleed:'кровоток', control:'контроль',
    stun:'оглуш', freeze:'заморозка', burst:'взрыв', discard:'сброс', crit:'крит',
    block:'блок', mana:'мана', execute:'казнь'
  };
  return map[tag] || tag;
}

const TAG_INFO = {
  charge: {title:'Заряд', desc:'Карта остаётся в руке и накапливает силу каждый ход.'},
  poison: {title:'Яд', desc:'В начале хода цель получает урон = стаки, затем они уменьшаются.'},
  burn: {title:'Ожог', desc:'В конце хода цель получает урон = стаки.'},
  bleed: {title:'Кровоток', desc:'Когда цель атакует, она получает урон = стаки (уменьшаются).'},
  control: {title:'Контроль', desc:'Ослабление и debuff-эффекты (слабость/уязвимость и т.п.).'},
  stun: {title:'Оглушение', desc:'Цель пропускает ход.'},
  freeze: {title:'Заморозка', desc:'Снижает урон цели, может пропустить ход.'},
  burst: {title:'Бурст', desc:'Прямой урон и добивание.'},
  discard: {title:'Сброс', desc:'Вращение колоды, взаимодействие со сбросом.'},
  crit: {title:'Крит', desc:'Повышенный шанс/урон критических ударов.'},
  block: {title:'Блок', desc:'Защита и удержание здоровья.'},
  mana: {title:'Мана', desc:'Генерация и экономия маны/энергии.'},
  execute: {title:'Казнь', desc:'Эффекты добивания слабых целей.'},
};

function statusInfo(key){
  const st = STATE?.content_summary?.statuses?.[key];
  if(!st) return null;
  return `${st.name}: ${st.desc}`;
}

function buffInfo(key){
  const bf = STATE?.content_summary?.buffs?.[key];
  if(!bf) return null;
  return `${bf.name}: ${bf.desc}`;
}

function describeEffect(eff){
  const op = eff?.op;
  if(op === 'damage') return `Урон: ${eff.amount?.base ?? eff.amount ?? 0}${eff.amount?.plus_charge ? ' (+заряд)' : ''}`;
  if(op === 'aoe_damage') return `Урон всем: ${eff.amount ?? 0}`;
  if(op === 'block') return `Блок: ${eff.amount ?? 0}`;
  if(op === 'heal') return `Лечение: ${eff.amount ?? 0}`;
  if(op === 'draw') return `Добор: ${eff.n ?? 0}`;
  if(op === 'gain_mana') return `+${eff.n ?? 0} маны`;
  if(op === 'discard_choose') return `Сброс по выбору: ${eff.n ?? 0}`;
  if(op === 'discard') return `Сброс случайных: ${eff.n ?? 0}`;
  if(op === 'apply' || op === 'apply_all'){
    const info = statusInfo(eff.status);
    return info ? `Статус: ${info} (${eff.stacks ?? 0})` : `Статус: ${eff.status} ${eff.stacks ?? ''}`;
  }
  if(op === 'gain_buff'){
    const info = buffInfo(eff.buff);
    return info ? `Баф: ${info}` : `Баф: ${eff.buff || ''}`;
  }
  if(op === 'choose_one') return 'Выбор одного эффекта';
  return null;
}

let CARD_TOOLTIP = null;
function ensureCardTooltip(){
  if(CARD_TOOLTIP) return CARD_TOOLTIP;
  const el = document.createElement('div');
  el.className = 'cardTooltip hidden';
  document.body.appendChild(el);
  CARD_TOOLTIP = el;
  return el;
}

function hideCardTooltip(){
  const el = ensureCardTooltip();
  el.classList.add('hidden');
}

function tooltipData(cardId, upgraded=false, fallback){
  let def = cardDefFromId(cardId, upgraded);
  if(!def && fallback){
    def = {...fallback};
  }
  if(!def) return null;
  if(upgraded && def.desc_up){
    def = {...def, desc: def.desc_up, effects: def.effects_up || def.effects};
  }
  return def;
}

function showCardTooltip(anchor, cardId, upgraded=false, fallback){
  const def = tooltipData(cardId, upgraded, fallback);
  if(!def) return;
  const el = ensureCardTooltip();
  const effects = (def.effects || []).map(describeEffect).filter(Boolean);
  const tags = def.tags || [];
  const tagLines = tags.map(t=>{
    const info = TAG_INFO[t];
    return info ? `<div><strong>${escapeHtml(info.title)}</strong> — ${escapeHtml(info.desc)}</div>` : `<div><strong>${escapeHtml(tagToRu(t))}</strong></div>`;
  }).join('');

  const body = `
    <div class="title">${escapeHtml(def.name || cardId)}${upgraded?'+':''}</div>
    <div class="section"><strong>${escapeHtml(rarityName(def.rarity||''))}</strong> · ${escapeHtml(typeName(def.type||''))}</div>
    ${tagLines ? `<div class="section">${tagLines}</div>` : ''}
    ${effects.length ? `<div class="section">${effects.map(escapeHtml).join('<br>')}</div>` : ''}
  `;
  el.innerHTML = body;

  const rect = anchor.getBoundingClientRect();
  const pad = 8;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let left = rect.right + pad;
  let top = rect.top;
  const width = Math.min(280, vw - 2*pad);
  if(left + width > vw - pad) left = Math.max(pad, rect.left - width - pad);
  el.classList.remove('hidden');
  const height = el.offsetHeight || 0;
  if(top + height > vh - pad) top = vh - height - pad;
  el.style.left = `${left}px`;
  el.style.top = `${Math.max(pad, top)}px`;
  el.classList.remove('hidden');
}

function attachCardTooltip(el, cardId, upgraded=false, fallback){
  if(!el) return;
  el.addEventListener('pointerenter', ()=> showCardTooltip(el, cardId, upgraded, fallback));
  el.addEventListener('pointerleave', hideCardTooltip);
  el.addEventListener('pointerdown', hideCardTooltip);
}

function setScreen(screenId){
  const screens = [
    '#screenMap','#screenCombat','#screenReward','#screenEvent','#screenEventPick',
    '#screenShop','#screenShopRemove','#screenCampfire','#screenCampfireUp',
    '#screenActEnd','#screenInherit','#screenVictory','#screenDefeat'
  ];
  for(const s of screens) show($(s), false);
  show($(screenId), true);
}

function updateHUD(){
  const run = STATE?.run;
  $('#hudFloor').textContent = `Этаж: ${run?.floor ?? '—'}`;
  $('#hudAct').textContent = `Акт: ${run?.act ?? '—'}`;
  $('#hudDiff').textContent = `Сложн: ${STATE?.settings?.difficulty ?? '—'}`;
  $('#hudGold').textContent = `Жетоны: ${run?.gold ?? '—'}`;
  if(run?.combat_view){
    const p = run.combat_view.player;
    $('#hudHP').textContent = `HP: ${p.hp}/${p.max_hp}`;
    $('#hudMana').textContent = `Мана: ${p.mana}/${p.mana_max}`;
  }else{
    $('#hudHP').textContent = `HP: ${run?.hp ?? '—'}/${run?.max_hp ?? '—'}`;
    $('#hudMana').textContent = `Мана: —/—`;
  }
}

// --- Renderers ---
function renderAll(){
  updateHUD();
  renderOverlays();
  renderScreen();
}

function renderOverlays(){
  // Меню/настройки/кодекс/колода управляются кнопками, но мы можем скрывать если экрана нет
}

function renderScreen(){
  const screen = STATE?.screen || 'MENU';

  if(screen === 'MENU'){
    show($('#overlayMenu'), true);
    setScreen('#screenMap'); // фон
    show($('#screenMap'), false);
    return;
  }else{
    show($('#overlayMenu'), false);
  }

  if(screen === 'SETTINGS'){
    show($('#overlaySettings'), true);
    return;
  }else{
    show($('#overlaySettings'), false);
  }

  // Нормальные экраны игры
  if(screen === 'MAP'){
    setScreen('#screenMap');
    renderMap();
  }else if(screen === 'COMBAT'){
    setScreen('#screenCombat');
    renderCombat();
  }else if(screen === 'REWARD'){
    setScreen('#screenReward');
    renderReward();
  }else if(screen === 'EVENT'){
    setScreen('#screenEvent');
    renderEvent();
  }else if(screen === 'EVENT_PICK'){
    setScreen('#screenEventPick');
    renderEventPick();
  }else if(screen === 'SHOP'){
    setScreen('#screenShop');
    renderShop();
  }else if(screen === 'SHOP_REMOVE'){
    setScreen('#screenShopRemove');
    renderShopRemove();
  }else if(screen === 'CAMPFIRE'){
    setScreen('#screenCampfire');
  }else if(screen === 'CAMPFIRE_UP'){
    setScreen('#screenCampfireUp');
    renderCampfireUp();
  }else if(screen === 'ACT_END'){
    setScreen('#screenActEnd');
    renderActEnd();
  }else if(screen === 'INHERIT'){
    setScreen('#screenInherit');
    renderInherit();
  }else if(screen === 'VICTORY'){
    setScreen('#screenVictory');
  }else if(screen === 'DEFEAT'){
    setScreen('#screenDefeat');
  }else{
    // fallback
    setScreen('#screenMap');
  }

  // combat pending modal
  if(STATE?.run?.combat_view?.pending){
    renderPendingModal();
  }else{
    show($('#modal'), false);
  }
}

function renderMap(){
  const run = STATE.run;
  const visited = new Set(run?.visited_nodes || []);
  const reachable = new Set((run?.room_choices || []).map(r=>r.id));
  const current = run?.current_node;
  const mapData = run?.path_map;
  const graph = $('#mapGraph');
  const canvas = $('#mapCanvas');
  const zoomInput = $('#mapZoom');
  const zoomLabel = $('#mapZoomLabel');
  if(zoomInput) zoomInput.value = String(MAP_ZOOM);
  if(zoomLabel) zoomLabel.textContent = `${Math.round(MAP_ZOOM*100)}%`;
  const prog = $('#mapProgress');
  prog.innerHTML = '';
  for(let f=1; f<=10; f++){
    const dot = document.createElement('div');
    dot.className = 'floorDot';
    if(f === run.floor) dot.classList.add('on');
    if([4,8,10].includes(f)) dot.classList.add('boss');
    dot.title = `Этаж ${f}`;
    prog.appendChild(dot);
  }

  const cols = $('#mapColumns');
  const svg = $('#mapLinks');
  cols.innerHTML = '';
  svg.innerHTML = '';

  if(mapData?.floors?.length){
    const lanes = mapData.lanes || 5;
    const colGap = 150;
    const rowGap = 130;
    const padX = 90;
    const padY = 90;
    const baseW = padX*2 + colGap * (mapData.floors.length - 1);
    const baseH = padY*2 + rowGap * (lanes - 1);
    const viewW = baseW * MAP_ZOOM;
    const viewH = baseH * MAP_ZOOM;
    svg.setAttribute('viewBox', `0 0 ${baseW} ${baseH}`);
    svg.setAttribute('width', `${viewW}`);
    svg.setAttribute('height', `${viewH}`);
    canvas.style.width = `${viewW}px`;
    canvas.style.height = `${viewH}px`;

    const positions = new Map();
    mapData.floors.forEach((layer, colIdx)=>{
      layer.forEach(node=>{
        const x = padX + colIdx * colGap;
        const y = padY + (node.lane || 0) * rowGap;
        positions.set(node.id, {x, y, node});
        const el = document.createElement('div');
        el.className = `mapNode type-${node.type}`;
        if(node.type === 'boss') el.classList.add('boss');
        if(visited.has(node.id)) el.classList.add('visited');
        if(node.id === current) el.classList.add('current');
        if(reachable.has(node.id)) el.classList.add('reachable');
        else if(node.floor === run.floor) el.classList.add('locked');
        el.innerHTML = `
          <div class="nodeLabel">${escapeHtml(node.label)}</div>
          <div class="nodeHint">${escapeHtml(node.hint)}</div>
          <div class="nodeFloor">Этаж ${node.floor}</div>
        `;
        el.style.left = `${x * MAP_ZOOM}px`;
        el.style.top = `${y * MAP_ZOOM}px`;
        if(reachable.has(node.id)){
          el.addEventListener('click', ()=> dispatch({type:'CHOOSE_ROOM', room_id: node.id}));
        }
        cols.appendChild(el);
      });
    });

    for(const [id, pos] of positions.entries()){
      const {x,y,node} = pos;
      for(const nid of (node.next || [])){
        const tgt = positions.get(nid);
        if(!tgt) continue;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', x);
        line.setAttribute('y1', y);
        line.setAttribute('x2', tgt.x);
        line.setAttribute('y2', tgt.y);
        let cls = 'mapEdge';
        if(visited.has(id) && (visited.has(nid) || current === nid)) cls += ' visited';
        if(reachable.has(nid) && current === id) cls += ' active';
        line.setAttribute('class', cls);
        svg.appendChild(line);
      }
    }

    const focusId = current || (run.room_choices || [])[0]?.id;
    const focusPos = focusId ? positions.get(focusId) : null;
    if(focusPos && graph){
      const targetX = focusPos.x * MAP_ZOOM - graph.clientWidth / 2;
      const targetY = focusPos.y * MAP_ZOOM - graph.clientHeight / 2;
      graph.scrollTo({left: Math.max(0, targetX), top: Math.max(0, targetY)});
    }
  }

  const choices = $('#roomChoices');
  choices.innerHTML = '';
  for(const room of (run.room_choices || [])){
    const btn = document.createElement('div');
    btn.className = 'roomBtn';
    btn.innerHTML = `
      <div class="label">${room.label}</div>
      <div class="hint">${room.hint}</div>
    `;
    btn.addEventListener('click', ()=> dispatch({type:'CHOOSE_ROOM', room_id: room.id}));
    choices.appendChild(btn);
  }
}

function renderCombat(){
  const cv = STATE.run.combat_view;
  const enemyRow = $('#enemyRow');
  enemyRow.innerHTML = '';

  cv.enemies.forEach((e, idx)=>{
    const div = document.createElement('div');
    div.className = 'entity enemy';
    div.dataset.enemyIndex = String(idx);
    div.innerHTML = `
      <div class="entityName">
        <span>${e.name}</span>
        <span class="chip">Блок ${e.block||0}</span>
      </div>
      <div class="bars">
        <div class="bar hp"><span>${e.hp}/${e.max_hp}</span></div>
      </div>
      <div class="entitySub">
        ${renderIntent(e.intent)}
      </div>
      <div class="statusRow">
        ${renderStatuses(e.statuses)}
      </div>
    `;
    enemyRow.appendChild(div);
  });

  // player panel
  $('#playerHPText').textContent = `${cv.player.hp}/${cv.player.max_hp}  (Блок ${cv.player.block||0})`;
  $('#playerManaText').textContent = `${cv.player.mana}/${cv.player.mana_max}  (крит ${Math.round(cv.player.crit*100)}%)`;
  $('#playerStatuses').innerHTML = renderStatuses(cv.player.statuses, cv.player.buffs);

  // piles
  $('#drawCount').textContent = String(cv.draw_count);
  $('#discardCount').textContent = String(cv.discard_count);
  $('#exhaustCount').textContent = String(cv.exhaust_count);

  // log
  const logBox = $('#combatLog');
  logBox.innerHTML = (cv.log || []).slice(-16).map(x=>`<div>• ${escapeHtml(x)}</div>`).join('');

  // hand
  const hand = $('#hand');
  hand.innerHTML = '';
  for(const c of (cv.hand || [])){
    hand.appendChild(makeHandCard(c));
  }

  // keyboard: space ends turn
}

function renderIntent(intent){
  if(!intent) return `<div class="intent"><b>…</b> <span class="muted">неизвестно</span></div>`;
  const t = intent.type;
  if(t === 'attack') return `<div class="intent"><b>АТАКА</b> ${intent.dmg}</div>`;
  if(t === 'attack_apply') return `<div class="intent"><b>АТАКА</b> ${intent.dmg} + ${tagToRu(intent.status)} ${intent.stacks}</div>`;
  if(t === 'apply') return `<div class="intent"><b>ДЕБАФ</b> ${tagToRu(intent.status)} ${intent.stacks}</div>`;
  if(t === 'apply_all') return `<div class="intent"><b>ДЕБАФ</b> ${tagToRu(intent.status)} ${intent.stacks}</div>`;
  if(t === 'block') return `<div class="intent"><b>БЛОК</b> ${intent.block}</div>`;
  if(t === 'heal') return `<div class="intent"><b>ХИЛ</b> ${intent.heal}</div>`;
  return `<div class="intent"><b>…</b> ${escapeHtml(intent.name||'')}</div>`;
}

function renderStatuses(statuses, buffs){
  let html = '';
  for(const [k,v] of Object.entries(statuses || {})){
    if(!v) continue;
    const st = STATE.content_summary?.statuses?.[k];
    html += `<div class="status"><span class="k">${escapeHtml(st?.name || k)}</span>${v}</div>`;
  }
  for(const [k,v] of Object.entries(buffs || {})){
    const bf = STATE.content_summary?.buffs?.[k];
    html += `<div class="status"><span class="k">${escapeHtml(bf?.name || k)}</span></div>`;
  }
  return html || `<div class="muted tiny">нет эффектов</div>`;
}

function makeHandCard(card){
  const wrap = document.createElement('div');
  wrap.className = `card rarity-${card.rarity} type-${card.type}`;
  wrap.dataset.uid = card.uid;
  wrap.dataset.target = card.target;
  wrap.dataset.tags = (card.tags||[]).join(',');
  const canPlay = canAffordCard(card);
  wrap.classList.toggle('noMana', !canPlay);
  wrap.innerHTML = `
    <div class="top">
      <div class="name">${escapeHtml(card.name)}</div>
      <div class="cost">${card.eff_cost ?? card.cost}</div>
    </div>
    <div class="desc">
      ${escapeHtml(card.desc)}
      ${card.stays_in_hand ? `<div class="tiny">ЗАРЯД: +${card.charge_per_turn}/ход (текущий +${card.charge||0})</div>` : ``}
      ${card.dmg_preview ? `<div class="tiny muted">≈ урон: ${card.dmg_preview}${card.charge?` (+${card.charge})`:''}</div>` : ``}
    </div>
    <div class="tags">${(card.tags||[]).slice(0,4).map(t=>`<span class="tag">${escapeHtml(tagToRu(t))}</span>`).join('')}</div>
  `;
  attachCardTooltip(wrap, card.id, !!card.up, card);
  enableDragToPlay(wrap, card);
  return wrap;
}

// --- Drag system ---
let DRAG = {
  active:false,
  uid:null,
  ghost:null,
  targetType:null
};

function findCardInHand(uid){
  return STATE?.run?.combat_view?.hand?.find(c=>c.uid === uid);
}

function canAffordCard(card){
  if(!card) return true;
  const mana = STATE?.run?.combat_view?.player?.mana ?? Infinity;
  const cost = card?.eff_cost ?? card?.cost ?? 0;
  return mana >= cost;
}

function setEnemiesTargetable(enabled, targetType){
  const needsEnemy = targetType === 'enemy' || targetType === 'any' || targetType === 'all_enemies';
  for(const e of $$('.entity.enemy')){
    e.classList.toggle('targetable', !!enabled && needsEnemy);
  }
}

function enableDragToPlay(cardEl, card){
  cardEl.addEventListener('pointerdown', (ev)=>{
    // только если бой и ход игрока
    if(STATE?.screen !== 'COMBAT') return;
    if(!canAffordCard(card)){
      toast('Не хватает маны.');
      return;
    }
    ev.preventDefault();
    DRAG.active = true;
    DRAG.uid = card.uid;
    DRAG.targetType = card.target;
    hideCardTooltip();

    const ghost = cardEl.cloneNode(true);
    ghost.classList.add('dragging');
    document.body.appendChild(ghost);
    DRAG.ghost = ghost;

    moveGhost(ev.clientX, ev.clientY);

    setEnemiesTargetable(true, card.target);

    cardEl.setPointerCapture(ev.pointerId);
  });

  cardEl.addEventListener('pointermove', (ev)=>{
    if(!DRAG.active || !DRAG.ghost) return;
    moveGhost(ev.clientX, ev.clientY);
    highlightDropTargets(ev.clientX, ev.clientY);
  });

  cardEl.addEventListener('pointerup', async (ev)=>{
    if(!DRAG.active) return;
    finalizeDrop(ev.clientX, ev.clientY);
    cleanupDrag();
  });

  cardEl.addEventListener('pointercancel', ()=>{
    cleanupDrag();
  });
}

function moveGhost(x,y){
  if(!DRAG.ghost) return;
  DRAG.ghost.style.left = `${x}px`;
  DRAG.ghost.style.top = `${y}px`;
}

function highlightDropTargets(x,y){
  for(const e of $$('.entity.enemy')) e.classList.remove('dropTarget');
  if(!(DRAG.targetType === 'enemy' || DRAG.targetType === 'any' || DRAG.targetType === 'all_enemies')) return;
  const el = document.elementFromPoint(x,y);
  const enemy = el?.closest?.('.entity.enemy');
  if(enemy) enemy.classList.add('dropTarget');
}

async function finalizeDrop(x,y){
  for(const e of $$('.entity.enemy')) e.classList.remove('dropTarget');
  setEnemiesTargetable(false);

  const view = findCardInHand(DRAG.uid);
  if(view && !canAffordCard(view)){
    toast('Не хватает маны.');
    return;
  }

  const el = document.elementFromPoint(x,y);
  const enemy = el?.closest?.('.entity.enemy');
  const targetType = DRAG.targetType;

  // all_enemies/none/self: цель не нужна (или self)
  if(targetType === 'enemy' || targetType === 'any'){
    if(enemy){
      const idx = parseInt(enemy.dataset.enemyIndex,10);
      await dispatch({type:'PLAY_CARD', uid: DRAG.uid, target: idx});
    }else{
      // если не попал — не разыгрываем
      toast('Нужно перетащить на врага.');
    }
  }else if(targetType === 'self'){
    await dispatch({type:'PLAY_CARD', uid: DRAG.uid, target: null});
  }else if(targetType === 'all_enemies' || targetType === 'none'){
    await dispatch({type:'PLAY_CARD', uid: DRAG.uid, target: null});
  }else{
    await dispatch({type:'PLAY_CARD', uid: DRAG.uid, target: null});
  }
}

function cleanupDrag(){
  DRAG.active = false;
  DRAG.uid = null;
  DRAG.targetType = null;
  if(DRAG.ghost){
    DRAG.ghost.remove();
    DRAG.ghost = null;
  }
  for(const e of $$('.entity.enemy')) e.classList.remove('dropTarget');
  setEnemiesTargetable(false);
  hideCardTooltip();
}

// --- Reward ---
function renderReward(){
  const run = STATE.run;
  const reward = run.reward;
  $('#rewardText').textContent = `+${reward.gold_gained} жетонов. Выбери одну карту (или пропусти).`;
  const box = $('#rewardChoices');
  box.innerHTML = '';
  for(const cid of reward.cards){
    box.appendChild(cardButton(cid, false, ()=> dispatch({type:'PICK_REWARD', card_id: cid})));
  }
}

function cardButton(cardId, upgraded, onClick, fallback){
  const d = cardDefFromId(cardId, upgraded);
  const fallbackDef = fallback || {id:cardId,name:cardId,rarity:'common',type:'skill',cost:0,desc:''};
  const c = d || fallbackDef;
  const holder = document.createElement('div');
  holder.className = 'cardBtn';
  holder.innerHTML = '';
  const view = {
    uid: '',
    name: c.name + (upgraded?'+':''),
    rarity: c.rarity,
    type: c.type,
    cost: c.cost,
    eff_cost: c.cost,
    desc: c.desc,
    tags: c.tags || [],
    target: c.target || 'none',
    stays_in_hand: !!c.stays_in_hand,
    charge_per_turn: c.charge_per_turn || 0,
    charge: 0
  };
  const cardEl = document.createElement('div');
  cardEl.className = `card rarity-${view.rarity} type-${view.type}`;
  cardEl.innerHTML = `
    <div class="top">
      <div class="name">${escapeHtml(view.name)}</div>
      <div class="cost">${view.cost}</div>
    </div>
    <div class="desc">${escapeHtml(view.desc)}</div>
    <div class="tags">${(view.tags||[]).slice(0,4).map(t=>`<span class="tag">${escapeHtml(tagToRu(t))}</span>`).join('')}</div>
  `;
  holder.appendChild(cardEl);
  holder.addEventListener('click', onClick);
  attachCardTooltip(holder, cardId, upgraded, c);
  return holder;
}

// --- Event ---
function renderEvent(){
  const ev = STATE.run.event;
  $('#eventTitle').textContent = ev.name;
  $('#eventDesc').textContent = ev.desc;
  const opts = $('#eventOptions');
  opts.innerHTML = '';
  for(const o of ev.options){
    const btn = document.createElement('div');
    btn.className = 'roomBtn';
    btn.innerHTML = `<div class="label">${escapeHtml(o.label)}</div>`;
    btn.addEventListener('click', ()=> dispatch({type:'EVENT_OPT', opt_id: o.id}));
    opts.appendChild(btn);
  }
}

function renderEventPick(){
  const pick = STATE.run.event_pick;
  const t = pick.type === 'remove' ? 'Удаление' : 'Улучшение';
  $('#eventPickTitle').textContent = t;
  $('#eventPickDesc').textContent = 'Выбор из 4 случайных карт.';
  const box = $('#eventPickChoices');
  box.innerHTML = '';
  for(const c of pick.choices){
    box.appendChild(cardButton(c.id, !!c.up, ()=> dispatch({type:'EVENT_PICK', uid: c.uid})));
  }
}

// --- Shop ---
function renderShop(){
  const shop = STATE.run.shop;
  const offers = $('#shopOffers');
  offers.innerHTML = '';
  shop.offers.forEach((it, idx)=>{
    const d = cardDefFromId(it.card_id,false);
    const holder = document.createElement('div');
    holder.className = 'cardBtn';
    holder.appendChild(cardButton(it.card_id,false, ()=> dispatch({type:'SHOP_BUY', what:'card', idx})));
    const price = document.createElement('div');
    price.className = 'chip';
    price.style.marginTop = '8px';
    price.textContent = `${it.price} жетонов`;
    holder.appendChild(price);
    offers.appendChild(holder);
  });

  const svc = $('#shopServices');
  svc.innerHTML = '';
  for(const s of shop.services){
    const btn = document.createElement('div');
    btn.className = 'roomBtn';
    btn.innerHTML = `<div class="label">${escapeHtml(s.label)}</div><div class="hint">${s.price} жетонов</div>`;
    btn.addEventListener('click', ()=> dispatch({type:'SHOP_BUY', what:s.id}));
    svc.appendChild(btn);
  }
}

function renderShopRemove(){
  const sr = STATE.run.shop_remove;
  const box = $('#shopRemoveChoices');
  box.innerHTML = '';
  for(const c of sr.choices){
    box.appendChild(cardButton(c.id, !!c.up, ()=> dispatch({type:'SHOP_REMOVE', uid: c.uid})));
  }
}

// --- Campfire ---
function renderCampfireUp(){
  const cu = STATE.run.campfire_up;
  const box = $('#campfireUpChoices');
  box.innerHTML = '';
  for(const c of cu.choices){
    box.appendChild(cardButton(c.id, !!c.up, ()=> dispatch({type:'CAMPFIRE_UP', uid: c.uid})));
  }
}

// --- Act end ---
function renderActEnd(){
  const ae = STATE.run.act_end;
  const dup = $('#actDupChoices');
  const rem = $('#actRemChoices');
  dup.innerHTML = '';
  rem.innerHTML = '';

  for(const c of ae.dup_choices){
    const holder = cardButton(c.id, !!c.up, ()=> dispatch({type:'ACT_END', kind:'dup', uid: c.uid}));
    if(ae.dup_done) holder.classList.add('muted');
    dup.appendChild(holder);
  }
  for(const c of ae.rem_choices){
    const holder = cardButton(c.id, !!c.up, ()=> dispatch({type:'ACT_END', kind:'rem', uid: c.uid}));
    if(ae.rem_done) holder.classList.add('muted');
    rem.appendChild(holder);
  }
}

// --- Inherit ---
function renderInherit(){
  const inh = STATE.inherit;
  const root = $('#inheritSlots');
  root.innerHTML = '';
  inh.slots.forEach((slot, sidx)=>{
    const box = document.createElement('div');
    box.className = 'inheritSlot';
    box.innerHTML = `<div class="slotTitle">Слот ${sidx+1}</div>`;
    const optWrap = document.createElement('div');
    optWrap.className = 'options';

    slot.options.forEach((opt, idx)=>{
      const d = cardDefFromId(opt.id, !!opt.up);
      const btn = document.createElement('div');
      btn.className = 'cardBtn';
      btn.appendChild(cardButton(opt.id, !!opt.up, ()=> dispatch({type:'INHERIT_PICK', slot:sidx, idx})));
      if(slot.picked && slot.picked.id === opt.id && !!slot.picked.up === !!opt.up){
        btn.classList.add('selectedGlow');
      }
      optWrap.appendChild(btn);
    });

    box.appendChild(optWrap);
    root.appendChild(box);
  });
}

// --- Pending modal (combat) ---
let MODAL_SELECTED = new Set();
function renderPendingModal(){
  const pending = STATE.run.combat_view.pending;
  const modal = $('#modal');
  const title = $('#modalTitle');
  const desc = $('#modalDesc');
  const body = $('#modalBody');
  const btnConfirm = $('#btnModalConfirm');
  const btnCancel = $('#btnModalCancel');

  show(modal, true);
  body.innerHTML = '';
  MODAL_SELECTED = new Set();

  btnCancel.onclick = ()=> { show(modal,false); };

  if(pending.type === 'discard_choose'){
    title.textContent = 'Сброс';
    desc.textContent = `Выбери ${pending.n} карт(ы) для сброса.`;
    const hand = STATE.run.combat_view.hand;
    hand.forEach(c=>{
      const el = cardButton(c.id, !!c.up, ()=> {
        if(MODAL_SELECTED.has(c.uid)) MODAL_SELECTED.delete(c.uid);
        else MODAL_SELECTED.add(c.uid);
        el.classList.toggle('selectedGlow', MODAL_SELECTED.has(c.uid));
      });
      // Заметим: cardButton создаёт «holder», внутри — card
      body.appendChild(el);
    });
    btnConfirm.onclick = ()=> {
      const uids = Array.from(MODAL_SELECTED).slice(0, pending.n);
      dispatch({type:'RESOLVE_PENDING', payload:{uids}});
    };
    return;
  }

  if(pending.type === 'take_from_discard'){
    title.textContent = 'Из сброса';
    desc.textContent = `Выбери карту из сброса.`;
    const disc = STATE.run.combat_view.discard_pile_cards || [];
    disc.slice().reverse().forEach(c=>{
      const el = cardButton(c.id, !!c.up, ()=> {
        // выбрать одну
        MODAL_SELECTED = new Set([c.uid]);
        for(const child of Array.from(body.children)){
          child.classList.remove('selectedGlow');
        }
        el.classList.add('selectedGlow');
      });
      // подменим uid, чтобы отправить именно uid карты
      el.dataset.uid = c.uid;
      // сделаем на клик сохранить uid
      el.addEventListener('click', ()=> {});
      body.appendChild(el);
      // запишем uid в holder, чтобы взять при confirm
      el._uid = c.uid;
    });
    btnConfirm.onclick = ()=> {
      const uid = Array.from(MODAL_SELECTED)[0];
      if(!uid){ toast('Выбери карту.'); return; }
      dispatch({type:'RESOLVE_PENDING', payload:{uid}});
    };
    return;
  }

  if(pending.type === 'choose_one'){
    title.textContent = 'Выбор эффекта';
    desc.textContent = 'Выбери один вариант.';
    pending.options.forEach((opt, idx)=>{
      const btn = document.createElement('div');
      btn.className = 'roomBtn';
      btn.innerHTML = `<div class="label">${escapeHtml(opt.label||('Вариант '+(idx+1)))}</div>`;
      btn.addEventListener('click', ()=> dispatch({type:'RESOLVE_PENDING', payload:{idx}}));
      body.appendChild(btn);
    });
    // тут не нужен confirm
    btnConfirm.onclick = ()=> { show(modal,false); };
    return;
  }

  title.textContent = 'Выбор';
  desc.textContent = '…';
  btnConfirm.onclick = ()=> { show(modal,false); };
}

// --- Codex ---
function openCodex(){
  show($('#overlayCodex'), true);
  renderCodex();
}
function renderCodex(){
  const list = $('#codexList');
  list.innerHTML = '';
  const q = ($('#codexSearch').value || '').toLowerCase().trim();
  const rar = $('#codexFilterRarity').value;
  const typ = $('#codexFilterType').value;

  if(!CONTENT){
    list.innerHTML = `<div class="muted">Контент ещё не загрузился.</div>`;
    return;
  }

  const cards = CONTENT.cards.map(x=>x.base);
  const filtered = cards.filter(c=>{
    if(rar && c.rarity !== rar) return false;
    if(typ && c.type !== typ) return false;
    if(!q) return true;
    const hay = `${c.name} ${c.desc} ${(c.tags||[]).join(' ')}`.toLowerCase();
    return hay.includes(q);
  });

  for(const c of filtered){
    const holder = document.createElement('div');
    holder.className = 'cardBtn';
    const cardEl = document.createElement('div');
    cardEl.className = `card rarity-${c.rarity} type-${c.type}`;
    cardEl.innerHTML = `
      <div class="top">
        <div class="name">${escapeHtml(c.name)}</div>
        <div class="cost">${c.cost}</div>
      </div>
      <div class="desc">${escapeHtml(c.desc)}</div>
      <div class="tags">
        <span class="tag">${escapeHtml(rarityName(c.rarity))}</span>
        <span class="tag">${escapeHtml(typeName(c.type))}</span>
        ${(c.tags||[]).slice(0,3).map(t=>`<span class="tag">${escapeHtml(tagToRu(t))}</span>`).join('')}
      </div>
    `;
    holder.appendChild(cardEl);
    list.appendChild(holder);
  }
}

// --- Deck overlay ---
function openDeck(){
  show($('#overlayDeck'), true);
  renderDeck();
}
function renderDeck(){
  const run = STATE.run;
  const deck = $('#deckList');
  deck.innerHTML = '';
  const dv = run?.deck_view || [];
  const tagSelect = $('#deckFilterTag');
  const currentTag = tagSelect.value;
  const tags = new Set(Object.keys(TAG_INFO));
  dv.forEach(c=> (c.tags||[]).forEach(t=> tags.add(t)));
  tagSelect.innerHTML = `<option value="">Все теги</option>` + Array.from(tags).sort().map(t=>`<option value="${t}">${escapeHtml(tagToRu(t))}</option>`).join('');
  if(currentTag && tags.has(currentTag)) tagSelect.value = currentTag;

  const rar = $('#deckFilterRarity').value;
  const typ = $('#deckFilterType').value;
  const tag = $('#deckFilterTag').value;
  const sort = $('#deckSort').value;

  const filtered = dv.filter(c=>{
    if(rar && c.rarity !== rar) return false;
    if(typ && c.type !== typ) return false;
    if(tag && !(c.tags||[]).includes(tag)) return false;
    return true;
  });

  const rarityOrder = {common:0, uncommon:1, rare:2, legendary:3};
  const sorters = {
    rarity:(a,b)=> (rarityOrder[a.rarity]-rarityOrder[b.rarity]) || a.type.localeCompare(b.type) || a.name.localeCompare(b.name),
    type:(a,b)=> a.type.localeCompare(b.type) || (a.cost - b.cost) || a.name.localeCompare(b.name),
    cost:(a,b)=> (a.cost - b.cost) || a.name.localeCompare(b.name),
  };
  const sorted = filtered.slice();
  if(sort !== 'default' && sorters[sort]) sorted.sort(sorters[sort]);

  $('#deckCount').textContent = `${sorted.length}/${dv.length} карт`;
  for(const c of sorted){
    deck.appendChild(cardButton(c.id, !!c.up, ()=>{}, c));
  }
}

// --- Utils ---
function escapeHtml(s){
  return String(s ?? '')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'",'&#039;');
}

// --- Wire UI buttons ---
function wire(){
  // Menu
  $('#btnMenu').addEventListener('click', ()=> show($('#overlayMenu'), true));
  $('#btnMenuCodex').addEventListener('click', openCodex);
  $('#btnMenuSettings').addEventListener('click', ()=> show($('#overlaySettings'), true));
  $('#btnContinue').addEventListener('click', ()=> { show($('#overlayMenu'), false); dispatch({type:'CONTINUE'}); });
  $('#btnNewRun').addEventListener('click', ()=> dispatch({type:'NEW_RUN'}));

  // Settings
  $('#btnSettings').addEventListener('click', ()=> show($('#overlaySettings'), true));
  $('#btnCloseSettings').addEventListener('click', ()=> show($('#overlaySettings'), false));
  $('#btnSaveSettings').addEventListener('click', ()=>{
    const v = parseInt($('#difficultyRange').value,10);
    dispatch({type:'SET_DIFFICULTY', difficulty: v});
    show($('#overlaySettings'), false);
  });
  $('#difficultyRange').addEventListener('input', ()=>{
    $('#difficultyValue').textContent = $('#difficultyRange').value;
  });

  // Codex
  $('#btnCodex').addEventListener('click', openCodex);
  $('#btnCloseCodex').addEventListener('click', ()=> show($('#overlayCodex'), false));
  $('#codexSearch').addEventListener('input', renderCodex);
  $('#codexFilterRarity').addEventListener('change', renderCodex);
  $('#codexFilterType').addEventListener('change', renderCodex);

  // Deck
  $('#btnDeck').addEventListener('click', openDeck);
  $('#btnCloseDeck').addEventListener('click', ()=> show($('#overlayDeck'), false));
  $('#deckFilterRarity').addEventListener('change', renderDeck);
  $('#deckFilterType').addEventListener('change', renderDeck);
  $('#deckFilterTag').addEventListener('change', renderDeck);
  $('#deckSort').addEventListener('change', renderDeck);

  // Map
  $('#mapZoom').addEventListener('input', (ev)=>{ MAP_ZOOM = Number(ev.target.value) || 1; renderMap(); });
  $('#mapResetView').addEventListener('click', ()=>{ MAP_ZOOM = 1; renderMap(); $('#mapGraph').scrollTo({left:0, top:0}); });

  // Reward
  $('#btnSkipReward').addEventListener('click', ()=> dispatch({type:'PICK_REWARD', card_id: null}));

  // Combat
  $('#btnEndTurn').addEventListener('click', ()=> dispatch({type:'END_TURN'}));
  document.addEventListener('keydown', (ev)=>{
    if(ev.code === 'Space' && STATE?.screen === 'COMBAT'){
      ev.preventDefault();
      dispatch({type:'END_TURN'});
    }
    if(ev.code === 'Escape'){
      show($('#overlayMenu'), true);
    }
  });

  // Shop
  $('#btnLeaveShop').addEventListener('click', ()=> dispatch({type:'SHOP_LEAVE'}));

  // Campfire
  $('#btnCampRest').addEventListener('click', ()=> dispatch({type:'CAMPFIRE', choice:'rest'}));
  $('#btnCampUpgrade').addEventListener('click', ()=> dispatch({type:'CAMPFIRE', choice:'upgrade'}));

  // Victory/Defeat
  $('#btnVictoryNewRun').addEventListener('click', ()=> dispatch({type:'NEW_RUN'}));
  $('#btnEndless').addEventListener('click', ()=> dispatch({type:'CONTINUE_ENDLESS'}));
  $('#btnDefeatNewRun').addEventListener('click', ()=> dispatch({type:'NEW_RUN'}));
  $('#btnDefeatMenu').addEventListener('click', ()=> { show($('#overlayMenu'), true); });
}

// --- init ---
wire();
bootstrap();
