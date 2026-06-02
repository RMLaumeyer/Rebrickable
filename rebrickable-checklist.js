const DATA_URL = 'rebrickable-checklist-data.json';
const STORAGE_KEY = 'rebrickable-checklist-progress-v1';

const grid = document.querySelector('#partsGrid');
const template = document.querySelector('#partTemplate');
const searchInput = document.querySelector('#searchInput');
const filterButtons = Array.from(document.querySelectorAll('[data-filter]'));
const exportButton = document.querySelector('#exportButton');
const resetButton = document.querySelector('#resetButton');
const completeCount = document.querySelector('#completeCount');
const totalCount = document.querySelector('#totalCount');
const ownedCount = document.querySelector('#ownedCount');
const neededCount = document.querySelector('#neededCount');
const sourceLabel = document.querySelector('#sourceLabel');

let parts = [];
let progress = loadProgress();
let activeFilter = 'all';
let searchTerm = '';

init();

async function init() {
  try {
    const payload = window.REBRICKABLE_CHECKLIST_DATA || await fetchChecklistData();
    parts = payload.parts;
    sourceLabel.textContent = `${payload.totalRows} parts from ${payload.source}, sorted by hue`;
    totalCount.textContent = parts.length;
    neededCount.textContent = parts.reduce((sum, part) => sum + part.quantity, 0);
    bindControls();
    render();
  } catch (error) {
    grid.innerHTML = `<div class="empty">${error.message}</div>`;
  }
}

async function fetchChecklistData() {
  const response = await fetch(DATA_URL);
  if (!response.ok) throw new Error(`Could not load ${DATA_URL}`);
  return response.json();
}

function bindControls() {
  searchInput.addEventListener('input', () => {
    searchTerm = searchInput.value.trim().toLowerCase();
    render();
  });

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeFilter = button.dataset.filter;
      filterButtons.forEach((item) => item.classList.toggle('active', item === button));
      render();
    });
  });

  exportButton.addEventListener('click', exportProgress);
  resetButton.addEventListener('click', () => {
    if (!confirm('Reset all checklist counts?')) return;
    progress = {};
    saveProgress();
    render();
  });
}

function render() {
  grid.innerHTML = '';
  const visibleParts = parts.filter(matchesView);

  if (!visibleParts.length) {
    grid.innerHTML = '<div class="empty">No matching parts.</div>';
    updateSummary();
    return;
  }

  for (const part of visibleParts) {
    const owned = getOwned(part);
    const card = template.content.firstElementChild.cloneNode(true);
    const img = card.querySelector('img');
    const qtyLine = card.querySelector('.qty-line');
    const name = card.querySelector('.part-name');
    const input = card.querySelector('input[type="number"]');
    const checkbox = card.querySelector('input[type="checkbox"]');
    const minus = card.querySelector('.minus');
    const plus = card.querySelector('.plus');

    card.classList.add(getStatus(part, owned));
    card.style.setProperty('--part-color', part.colorHex);
    img.src = part.imageUrl;
    img.alt = `${part.colorName} ${part.name}`;
    img.loading = 'lazy';
    img.addEventListener('error', () => {
      if (img.src !== part.fallbackImageUrl) img.src = part.fallbackImageUrl;
    }, { once: true });

    qtyLine.textContent = `${part.quantity} x ${part.part}`;
    qtyLine.title = part.colorName;
    qtyLine.style.color = readableAccent(part.colorHex);
    name.textContent = part.name;
    name.title = `${part.colorName} ${part.name}`;
    input.value = owned;
    input.max = Math.max(part.quantity, owned);
    checkbox.checked = owned >= part.quantity;

    minus.addEventListener('click', () => setOwned(part, owned - 1));
    plus.addEventListener('click', () => setOwned(part, owned + 1));
    input.addEventListener('change', () => setOwned(part, Number(input.value)));
    checkbox.addEventListener('change', () => setOwned(part, checkbox.checked ? part.quantity : 0));

    grid.append(card);
  }

  updateSummary();
}

function matchesView(part) {
  const owned = getOwned(part);
  const status = getStatus(part, owned);
  const haystack = `${part.part} ${part.colorName} ${part.name}`.toLowerCase();
  return (activeFilter === 'all' || activeFilter === status) && (!searchTerm || haystack.includes(searchTerm));
}

function getOwned(part) {
  return Math.max(0, Number(progress[part.id] || 0));
}

function setOwned(part, value) {
  const owned = Math.max(0, Math.floor(Number.isFinite(value) ? value : 0));
  if (owned === 0) delete progress[part.id];
  else progress[part.id] = owned;
  saveProgress();
  render();
}

function getStatus(part, owned) {
  if (owned >= part.quantity) return 'complete';
  if (owned > 0) return 'partial';
  return 'missing';
}

function updateSummary() {
  let complete = 0;
  let ownedPieces = 0;
  for (const part of parts) {
    const owned = getOwned(part);
    if (owned >= part.quantity) complete += 1;
    ownedPieces += Math.min(owned, part.quantity);
  }
  completeCount.textContent = complete;
  ownedCount.textContent = ownedPieces;
}

function loadProgress() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function saveProgress() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
}

function exportProgress() {
  const rows = [['Part', 'Color', 'Required', 'Owned', 'Complete']];
  for (const part of parts) {
    const owned = getOwned(part);
    rows.push([part.part, part.colorName, part.quantity, owned, owned >= part.quantity ? 'Yes' : 'No']);
  }
  const csv = rows.map((row) => row.map(csvCell).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'rebrickable-checklist-progress.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value) {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function readableAccent(hex) {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  const contrast = (r * 0.299 + g * 0.587 + b * 0.114) / 255;
  return contrast > 0.65 ? '#315d12' : '#3f6517';
}
