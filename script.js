// Constants
const RADIUS = 16;
const COLOR_NODE_IDLE = getCssVar('--muted');
const COLOR_NODE_VISITED = getCssVar('--amber');
const COLOR_EDGE = getCssVar('--edge');
const COLOR_EDGE_CURRENT = getCssVar('--blue');
const COLOR_EDGE_REJECT = getCssVar('--red');
const COLOR_EDGE_MST = getCssVar('--green');
const COLOR_TEXT = getCssVar('--text');

function getCssVar(name) {
	return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// State
let totalVertices = 5;
let placingVerticesRemaining = totalVertices;
let isAnimating = false;
let startVertex = null;

// Playback timeline
let steps = [];
let kruskalTotal = null;
let primTotal = null;
let stepIndex = -1; // index of last applied step
let isPlaying = false;
let playTimer = null;

/** @type {Map<number, {x:number,y:number}>} */
const vertexPositions = new Map();
/** @type {Map<number, {circleId:number,labelId:number}>} */
const vertexItems = new Map();
/** @type {Array<[number,number,number]>} */
const edges = [];
/** @type {Map<string, {lineId:number, labelId:number}>} */
const edgeItems = new Map();
/** @type {Array<number>} */
let vertexClickBuffer = [];

// Canvas setup
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');

// Simple retained-mode drawing model
let drawCommands = [];
let idCounter = 1;

function addCommand(cmd) {
	cmd.id = idCounter++;
	drawCommands.push(cmd);
	requestPaint();
	return cmd.id;
}

function updateCommand(id, props) {
	const cmd = drawCommands.find(c => c.id === id);
	if (!cmd) return;
	Object.assign(cmd, props);
	requestPaint();
}

function removeCommand(id) {
	const idx = drawCommands.findIndex(c => c.id === id);
	if (idx !== -1) {
		drawCommands.splice(idx, 1);
		requestPaint();
	}
}

let rafToken = null;
function requestPaint() {
	if (rafToken) return;
	rafToken = requestAnimationFrame(() => {
		rafToken = null;
		paint();
	});
}

function paint() {
	ctx.clearRect(0, 0, canvas.width, canvas.height);
	// Draw edges first
	for (const cmd of drawCommands) {
		if (cmd.type !== 'line') continue;
		ctx.lineWidth = cmd.width || 3;
		ctx.strokeStyle = cmd.color || COLOR_EDGE;
		ctx.beginPath();
		ctx.moveTo(cmd.x1, cmd.y1);
		ctx.lineTo(cmd.x2, cmd.y2);
		ctx.stroke();
		// weight label
		if (cmd.text) {
			ctx.fillStyle = COLOR_TEXT;
			ctx.font = '12px Segoe UI';
			ctx.textAlign = 'center';
			ctx.fillText(cmd.text, (cmd.x1 + cmd.x2) / 2, (cmd.y1 + cmd.y2) / 2 - 10);
		}
	}
	// Draw nodes above edges
	for (const cmd of drawCommands) {
		if (cmd.type !== 'circle') continue;
		ctx.fillStyle = cmd.fill || COLOR_NODE_IDLE;
		ctx.strokeStyle = getCssVar('--stroke');
		ctx.lineWidth = 2;
		ctx.beginPath();
		ctx.arc(cmd.x, cmd.y, cmd.r, 0, Math.PI * 2);
		ctx.fill();
		ctx.stroke();
		ctx.fillStyle = COLOR_TEXT;
		ctx.font = 'bold 12px Segoe UI';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(String(cmd.label), cmd.x, cmd.y);
	}
}

// Helpers
function setStatus(msg) {
	statusEl.textContent = msg;
}

function edgeKey(u, v) {
	return u < v ? `${u}-${v}` : `${v}-${u}`;
}

function removeEdge(u, v, w) {
	const key = edgeKey(u, v);
	const item = edgeItems.get(key);
	if (item) {
		removeCommand(item.lineId);
		edgeItems.delete(key);
	}
	// Remove one matching edge (unordered endpoints and same weight)
	const idx = edges.findIndex(([a, b, ww]) => ww === w && ((a === u && b === v) || (a === v && b === u)));
	if (idx !== -1) edges.splice(idx, 1);
}

function findVertexAt(x, y) {
	for (const [vid, pos] of vertexPositions.entries()) {
		const dx = pos.x - x;
		const dy = pos.y - y;
		if (dx * dx + dy * dy <= RADIUS * RADIUS) return vid;
	}
	return null;
}

// UI wiring
document.getElementById('btnSetVertices').addEventListener('click', () => {
	if (isAnimating) return;
	const n = parseInt(document.getElementById('totalVertices').value, 10);
	if (!Number.isInteger(n) || n <= 0) {
		alert('Enter a positive integer for total vertices.');
		return;
	}
	resetAll();
	totalVertices = n;
	placingVerticesRemaining = n;
	setStatus(`Place ${n} vertices by clicking on canvas.`);
});

document.getElementById('btnResetColors').addEventListener('click', () => {
	if (isAnimating) return;
	for (const [key, item] of edgeItems.entries()) {
		updateCommand(item.lineId, { color: COLOR_EDGE });
	}
	for (const [vid, item] of vertexItems.entries()) {
		updateCommand(item.circleId, { fill: COLOR_NODE_IDLE });
	}
	setStatus('Colors reset.');
});

document.getElementById('btnRunBoth').addEventListener('click', async () => {
	if (isAnimating) return;
	if (vertexPositions.size !== totalVertices) {
		alert(`Place exactly ${totalVertices} vertices first.`);
		return;
	}
	if (edges.length === 0) {
		alert('Add at least one edge.');
		return;
	}
	const startStr = prompt(`Enter starting vertex (0..${totalVertices - 1}) for both Kruskal and Prim:`);
	if (startStr === null) return;
	const start = Number(startStr);
	if (!Number.isInteger(start) || start < 0 || start >= totalVertices) { alert('Invalid start vertex.'); return; }
	startVertex = start;
	// Build combined steps and start playback
	prepareSceneNeutral();
	kruskalTotal = null; primTotal = null;
	steps = [
		...buildKruskalSteps(startVertex),
		...buildPrimSteps(startVertex),
		{ t: 'status', msg: () => finalTotalsMessage() }
	];
	stepIndex = -1;
	setStatus('Prepared Kruskal → Prim. Press Play or use Next.');
	startAutoPlay();
});

document.getElementById('btnRunKruskal').addEventListener('click', async () => {
	if (isAnimating) return;
	if (vertexPositions.size !== totalVertices) { alert(`Place exactly ${totalVertices} vertices first.`); return; }
	if (edges.length === 0) { alert('Add at least one edge.'); return; }
	const startStr = prompt(`Enter starting vertex for Kruskal (0..${totalVertices - 1}) or leave blank:`);
	let start = null;
	if (startStr !== null && startStr.trim() !== '') {
		const v = Number(startStr);
		if (Number.isInteger(v) && v >= 0 && v < totalVertices) start = v; else { alert('Invalid start vertex.'); return; }
	}
	prepareSceneNeutral();
	kruskalTotal = null; primTotal = null;
	steps = [
		...buildKruskalSteps(start),
		{ t: 'status', msg: () => totalsMessage('Kruskal', kruskalTotal) }
	];
	stepIndex = -1;
	setStatus('Prepared Kruskal steps. Press Play or use Next.');
	startAutoPlay();
});

document.getElementById('btnRunPrim').addEventListener('click', async () => {
	if (isAnimating) return;
	if (vertexPositions.size !== totalVertices) { alert(`Place exactly ${totalVertices} vertices first.`); return; }
	if (edges.length === 0) { alert('Add at least one edge.'); return; }
	const startStr = prompt(`Enter starting vertex for Prim (0..${totalVertices - 1}):`);
	if (startStr === null) return;
	const start = Number(startStr);
	if (!Number.isInteger(start) || start < 0 || start >= totalVertices) { alert('Invalid start vertex.'); return; }
	prepareSceneNeutral();
	kruskalTotal = null; primTotal = null;
	steps = [
		...buildPrimSteps(start),
		{ t: 'status', msg: () => totalsMessage('Prim', primTotal) }
	];
	stepIndex = -1;
	setStatus('Prepared Prim steps. Press Play or use Next.');
	startAutoPlay();
});

canvas.addEventListener('click', (e) => {
	if (isAnimating) return;
	const rect = canvas.getBoundingClientRect();
	const x = (e.clientX - rect.left) * (canvas.width / rect.width);
	const y = (e.clientY - rect.top) * (canvas.height / rect.height);
	if (placingVerticesRemaining > 0) {
		const vid = vertexPositions.size;
		addVertex(vid, x, y);
		placingVerticesRemaining--;
		if (placingVerticesRemaining === 0) {
			setStatus('Vertices placed. Click two vertices to add edges.');
		} else {
			setStatus(`Place ${placingVerticesRemaining} more vertices.`);
		}
		return;
	}
	const clicked = findVertexAt(x, y);
	if (clicked === null) return;
	vertexClickBuffer.push(clicked);
	if (vertexClickBuffer.length === 2) {
		const [u, v] = vertexClickBuffer;
		vertexClickBuffer = [];
		if (u === v) return;
		const key = edgeKey(u, v);
		if (edgeItems.has(key)) { alert('Edge already exists.'); return; }
		const wStr = prompt(`Enter weight for edge (${u}, ${v}):`);
		if (wStr === null) return;
		const w = Number(wStr);
		if (!Number.isFinite(w) || w < 0) { alert('Enter a non-negative number.'); return; }
		addEdge(u, v, w);
		setStatus(`Added edge (${u}, ${v}, ${w}).`);
	}
});

// Graph ops
function addVertex(vid, x, y) {
	const circleId = addCommand({ type: 'circle', x, y, r: RADIUS, fill: COLOR_NODE_IDLE, label: vid });
	vertexPositions.set(vid, { x, y });
	vertexItems.set(vid, { circleId, labelId: 0 });
}

function addEdge(u, v, w) {
	const p1 = vertexPositions.get(u);
	const p2 = vertexPositions.get(v);
	const lineId = addCommand({ type: 'line', x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y, color: COLOR_EDGE, width: 3, text: String(w) });
	edges.push([u, v, w]);
	edgeItems.set(edgeKey(u, v), { lineId, labelId: 0 });
}

function resetAll() {
	drawCommands = [];
	idCounter = 1;
	vertexPositions.clear();
	vertexItems.clear();
	edges.length = 0;
	edgeItems.clear();
	vertexClickBuffer = [];
	placingVerticesRemaining = totalVertices;
	requestPaint();
}

// Build step timelines
function buildKruskalSteps(start) {
	/** @type {Array<any>} */
	const s = [];
	// scene reset
	s.push({ t: 'reset' });
	if (start != null && vertexItems.has(start)) {
		s.push({ t: 'status', msg: `Kruskal: starting at ${start}` });
		s.push({ t: 'node', v: start, color: COLOR_NODE_VISITED });
	}
	const sorted = [...edges].sort((a, b) => a[2] - b[2]);
	const parent = Array.from({ length: totalVertices }, (_, i) => i);
	const rank = Array(totalVertices).fill(0);
	function find(x) { return parent[x] === x ? x : (parent[x] = find(parent[x])); }
	function union(a, b) {
		let ra = find(a), rb = find(b);
		if (ra === rb) return false;
		if (rank[ra] < rank[rb]) parent[ra] = rb;
		else if (rank[ra] > rank[rb]) parent[rb] = ra;
		else { parent[rb] = ra; rank[ra]++; }
		return true;
	}
	let total = 0;
	for (const [u, v, w] of sorted) {
		const key = edgeKey(u, v);
		s.push({ t: 'edge', key, color: COLOR_EDGE_CURRENT });
		s.push({ t: 'status', msg: `Kruskal: considering (${u}, ${v}) w=${w}` });
		if (union(u, v)) {
			s.push({ t: 'edge', key, color: COLOR_EDGE_MST });
			total += w;
			s.push({ t: 'status', msg: () => `Kruskal: accepted (${u}, ${v}) | MST total (green) = ${total}` });
			s.push({ t: 'node', v: u, color: COLOR_NODE_VISITED });
			s.push({ t: 'node', v: v, color: COLOR_NODE_VISITED });
		} else {
			s.push({ t: 'edge', key, color: COLOR_EDGE_REJECT });
			s.push({ t: 'status', msg: `Kruskal: rejected (${u}, ${v})` });
			s.push({ t: 'edge', key, color: COLOR_EDGE }); // revert to neutral
		}
	}
	// record total at end
	s.push({ t: 'setTotal', alg: 'kruskal', value: () => total });
	s.push({ t: 'status', msg: () => totalsMessage('Kruskal', total) });
	return s;
}

function buildPrimSteps(start) {
	/** @type {Array<any>} */
	const s = [];
	s.push({ t: 'reset' });
	if (!Number.isInteger(start) || start < 0 || start >= totalVertices) {
		s.push({ t: 'status', msg: 'Prim: invalid start vertex.' });
		return s;
	}
	/** @type {Map<number, Array<[number,number,number]>>} */
	const adj = new Map();
	for (let i = 0; i < totalVertices; i++) adj.set(i, []);
	for (const [u, v, w] of edges) {
		adj.get(u).push([w, u, v]);
		adj.get(v).push([w, v, u]);
	}
	const visited = new Set();
	const heap = [];
	function pushEdges(u) {
		for (const [w, _u, v] of adj.get(u)) if (!visited.has(v)) heapPush(heap, [w, u, v]);
	}
	visited.add(start);
	s.push({ t: 'node', v: start, color: COLOR_NODE_VISITED });
	s.push({ t: 'status', msg: `Prim: visited ${start}` });
	pushEdges(start);
	let total = 0;
	while (heap.length && visited.size < totalVertices) {
		const [w, u, v] = heapPop(heap);
		const key = edgeKey(u, v);
		s.push({ t: 'edge', key, color: COLOR_EDGE_CURRENT });
		s.push({ t: 'status', msg: `Prim: considering (${u}, ${v}) w=${w}` });
		if (visited.has(v)) {
			s.push({ t: 'edge', key, color: COLOR_EDGE_REJECT });
			s.push({ t: 'status', msg: `Prim: rejected (${u}, ${v})` });
			s.push({ t: 'edge', key, color: COLOR_EDGE });
			continue;
		}
		visited.add(v);
		s.push({ t: 'edge', key, color: COLOR_EDGE_MST });
		total += w;
		s.push({ t: 'status', msg: () => `Prim: accepted (${u}, ${v}) | MST total (green) = ${total}` });
		s.push({ t: 'node', v, color: COLOR_NODE_VISITED });
		pushEdges(v);
	}
	// record total at end
	s.push({ t: 'setTotal', alg: 'prim', value: () => total });
	s.push({ t: 'status', msg: () => totalsMessage('Prim', total) });
	return s;
}

function prepareSceneNeutral() {
	for (const [key, item] of edgeItems.entries()) updateCommand(item.lineId, { color: COLOR_EDGE });
	for (const [vid, item] of vertexItems.entries()) updateCommand(item.circleId, { fill: COLOR_NODE_IDLE });
}

function applyStep(step) {
	if (step.t === 'status') setStatus(typeof step.msg === 'function' ? step.msg() : step.msg);
	else if (step.t === 'reset') prepareSceneNeutral();
	else if (step.t === 'edge') {
		const item = edgeItems.get(step.key);
		if (item) updateCommand(item.lineId, { color: step.color });
	}
	else if (step.t === 'node') {
		const item = vertexItems.get(step.v);
		if (item) updateCommand(item.circleId, { fill: step.color });
	}
	else if (step.t === 'setTotal') {
		const value = typeof step.value === 'function' ? step.value() : step.value;
		if (step.alg === 'kruskal') kruskalTotal = value; else if (step.alg === 'prim') primTotal = value;
	}
}

function replayTo(index) {
	prepareSceneNeutral();
	for (let i = 0; i <= index; i++) applyStep(steps[i]);
}

function startAutoPlay() {
	stopAutoPlay();
	isPlaying = true;
	updatePlayButton();
	playTimer = setInterval(() => {
		if (stepIndex + 1 >= steps.length) { stopAutoPlay(); return; }
		stepIndex++;
		applyStep(steps[stepIndex]);
	}, 600);
}

function stopAutoPlay() {
	if (playTimer) clearInterval(playTimer);
	playTimer = null;
	isPlaying = false;
	updatePlayButton();
}

function updatePlayButton() {
	const btn = document.getElementById('btnPlayPause');
	btn.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
}

document.getElementById('btnPlayPause').addEventListener('click', () => {
	if (!steps.length) return;
	if (isPlaying) stopAutoPlay(); else startAutoPlay();
});

document.getElementById('btnNext').addEventListener('click', () => {
	if (!steps.length) return;
	stopAutoPlay();
	if (stepIndex + 1 < steps.length) {
		stepIndex++;
		applyStep(steps[stepIndex]);
	}
});

document.getElementById('btnPrev').addEventListener('click', () => {
	if (!steps.length) return;
	stopAutoPlay();
	if (stepIndex >= 0) {
		stepIndex--;
		replayTo(stepIndex);
	}
});

function sleep(ms) { return new Promise(res => setTimeout(res, ms)); }

// Binary heap helpers for [w,u,v]
function heapPush(h, val) { h.push(val); siftUp(h, h.length - 1); }
function heapPop(h) { if (h.length === 0) return null; const top = h[0]; const last = h.pop(); if (h.length) { h[0] = last; siftDown(h, 0); } return top; }
function siftUp(h, i) {
	while (i > 0) {
		const p = (i - 1) >> 1;
		if (h[p][0] <= h[i][0]) break;
		[ h[p], h[i] ] = [ h[i], h[p] ];
		i = p;
	}
}
function siftDown(h, i) {
	while (true) {
		let l = i * 2 + 1, r = i * 2 + 2, m = i;
		if (l < h.length && h[l][0] < h[m][0]) m = l;
		if (r < h.length && h[r][0] < h[m][0]) m = r;
		if (m === i) break;
		[ h[m], h[i] ] = [ h[i], h[m] ];
		i = m;
	}
}

function totalsMessage(name, total) {
	if (total == null) return `${name} completed.`;
	return `${name} completed. Total weight = ${total}`;
}

function finalTotalsMessage() {
	const parts = [];
	if (kruskalTotal != null) parts.push(`Kruskal: ${kruskalTotal}`);
	if (primTotal != null) parts.push(`Prim: ${primTotal}`);
	if (!parts.length) return 'Completed Kruskal → Prim.';
	return `Completed Kruskal → Prim. Totals — ${parts.join(', ')}`;
}

// Initialize
setStatus(`Place ${totalVertices} vertices by clicking on canvas.`);

