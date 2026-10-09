'use strict';

const byId = id => document.getElementById(id);
const defaultGraphId = document.body.dataset.defaultGraphId;
let availableGraphs = [];
let activeGraphId = null;
let graph = null;
let domains = [];
let cy = null;
let loadVersion = 0;
let graphLoading = false;
let selectedNodeId = null;
let selectedEdgeId = null;
let suggestedExistingNodeId = null;
let suggestedDuplicateNodeId = null;

const themeColors = {
  'Platform': '#2563eb',
  'Design tools': '#7c3aed',
  'Data': '#0f766e',
  'Visualization': '#be185d',
  'Logic': '#b45309',
  'Connectivity': '#0e7490',
  'Security': '#b91c1c',
  'Software': '#4f46e5',
  'Delivery': '#9a3412',
  'AI': '#6d28d9',
  'Business': '#166534',
  'Ungrouped': '#475569'
};

function themeFor(node) {
  const theme = node.layer?.trim();
  if (!theme) return 'Ungrouped';
  return Object.keys(themeColors).find(name => name.toLowerCase() === theme.toLowerCase()) || theme;
}

function colorForTheme(theme) {
  if (Object.prototype.hasOwnProperty.call(themeColors, theme)) return themeColors[theme];
  let hash = 0;
  for (const character of theme.toLowerCase()) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return `hsl(${hash % 360}, 65%, 35%)`;
}

function renderThemeLegend() {
  const counts = new Map();
  for (const node of graph.nodes) {
    const theme = themeFor(node);
    counts.set(theme, (counts.get(theme) || 0) + 1);
  }
  const rows = [...counts].sort(([a], [b]) => a.localeCompare(b)).map(([theme, count]) => {
    const row = document.createElement('div');
    row.className = 'theme-row';
    const swatch = document.createElement('span');
    swatch.className = 'theme-swatch';
    swatch.style.backgroundColor = colorForTheme(theme);
    row.append(swatch, textElement('span', `${theme} (${count})`));
    return row;
  });
  byId('themeLegend').replaceChildren(...rows);
}

function jsonOptions(method, payload) {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)};
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Request failed (${response.status})`);
  }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function textElement(tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  return element;
}

function showMessage(title, message) {
  byId('details').replaceChildren(
    textElement('h3', title),
    textElement('div', message, 'muted')
  );
}

function refreshAddButton() {
  const term = byId('term').value.trim().toLowerCase();
  const exists = term && graph?.nodes.some(node => node.label.trim().toLowerCase() === term);
  byId('addButton').disabled = graphLoading || !activeGraphId || !!exists
    || !!suggestedDuplicateNodeId;
}

function refreshConnectButton() {
  const button = byId('connectSuggestionButton');
  button.hidden = !suggestedExistingNodeId;
  button.disabled = !suggestedExistingNodeId || !byId('parent').value
    || !byId('parentRelation').value.trim();
}

function showNode(node) {
  selectedNodeId = node.id;
  selectedEdgeId = null;
  const details = byId('details');
  details.replaceChildren(textElement('h3', node.label));
  details.append(textElement('span', node.type, 'pill'));
  if (node.layer) details.append(textElement('span', node.layer, 'pill'));
  if (node.description) details.append(textElement('p', node.description));
  details.append(textElement('div', `id: ${node.id}`, 'muted'));
  byId('edgeEditor').hidden = true;
  byId('nodeEditor').hidden = false;
  byId('nodeIdText').textContent = `id: ${node.id}`;
  byId('editNodeLabel').value = node.label;
  byId('editNodeType').value = node.type;
  byId('editNodeLayer').value = node.layer || '';
  byId('editNodeDescription').value = node.description || '';
  byId('nodeEditStatus').textContent = '';
  byId('edgeSource').value = node.id;
  if (byId('edgeTarget').value === node.id) {
    const other = graph.nodes.find(item => item.id !== node.id);
    if (other) byId('edgeTarget').value = other.id;
  }
}

function showEdge(edge) {
  selectedEdgeId = edge.id;
  selectedNodeId = null;
  const labelFor = id => graph.nodes.find(node => node.id === id)?.label || id;
  const description = `${labelFor(edge.source)} —${edge.relation}→ ${labelFor(edge.target)}`;
  byId('details').replaceChildren(
    textElement('h3', 'Relationship'),
    textElement('p', description),
    textElement('div', `id: ${edge.id}`, 'muted')
  );
  byId('nodeEditor').hidden = true;
  byId('edgeEditor').hidden = false;
  byId('edgeIdText').textContent = `id: ${edge.id}`;
  byId('editEdgeSource').value = edge.source;
  byId('editEdgeRelation').value = edge.relation;
  byId('editEdgeTarget').value = edge.target;
  byId('edgeEditStatus').textContent = '';
}

function chooseGraphId() {
  const requested = new URL(window.location.href).searchParams.get('graph');
  if (availableGraphs.some(item => item.id === requested)) return requested;
  if (availableGraphs.some(item => item.id === defaultGraphId)) return defaultGraphId;
  return availableGraphs[0].id;
}

function populateControls() {
  const filter = byId('filter');
  filter.replaceChildren(new Option(domains.length ? 'All domains' : 'No domains', ''));
  for (const domain of domains) filter.add(new Option(domain.label, domain.id));
  filter.disabled = domains.length === 0;

  const parent = byId('parent');
  parent.replaceChildren(new Option('Standalone (no connection)', ''));
  const sortedNodes = [...graph.nodes].sort((a, b) => a.label.localeCompare(b.label));
  for (const node of sortedNodes) {
    parent.add(new Option(node.label, node.id));
  }
  for (const selectId of ['edgeSource', 'edgeTarget', 'editEdgeSource', 'editEdgeTarget']) {
    const select = byId(selectId);
    select.replaceChildren();
    for (const node of sortedNodes) select.add(new Option(node.label, node.id));
  }
  if (sortedNodes.length > 1) byId('edgeTarget').value = sortedNodes[1].id;
  byId('addEdgeButton').disabled = sortedNodes.length < 2;

  const relations = new Set([
    'contains', 'runs on', 'configured by', 'belongs to',
    'communicates with', 'inherits from', 'executed in scope'
  ]);
  for (const edge of graph.edges) relations.add(edge.relation);
  byId('relationTypes').replaceChildren(
    ...[...relations].sort().map(relation => new Option(relation, relation))
  );

  const themes = new Set([
    'Platform', 'Design tools', 'Data', 'Visualization', 'Logic',
    'Connectivity', 'Security'
  ]);
  for (const node of graph.nodes) if (node.layer) themes.add(node.layer);
  byId('themeTypes').replaceChildren(
    ...[...themes].sort().map(theme => new Option(theme, theme))
  );

  byId('parentRelation').value = 'contains';
  byId('parentRelation').disabled = true;
  byId('classifyButton').disabled = false;
  byId('suggestion').textContent = '';
}

function renderGraph() {
  if (cy) cy.destroy();
  const nodeColors = new Map(graph.nodes.map(node => [
    node.id, colorForTheme(themeFor(node))
  ]));
  const elements = [
    ...graph.nodes.map(node => ({data: {...node, themeColor: nodeColors.get(node.id)}})),
    ...graph.edges.map(edge => ({data: {
      ...edge, themeColor: nodeColors.get(edge.target) || themeColors.Ungrouped
    }}))
  ];
  cy = cytoscape({
    container: byId('cy'),
    elements,
    style: [
      {selector: 'node', style: {'label': 'data(label)', 'background-color': 'data(themeColor)', 'color': '#fff', 'font-size': 11, 'text-valign': 'center', 'text-halign': 'center', 'width': 34, 'height': 34}},
      {selector: 'node[type="domain"]', style: {'width': 70, 'height': 70, 'font-size': 13, 'font-weight': 'bold', 'text-wrap': 'wrap', 'text-max-width': 90}},
      {selector: 'edge', style: {'label': 'data(relation)', 'font-size': 9, 'color': '#b8c0cc', 'text-background-color': '#0d1117', 'text-background-opacity': 0.85, 'text-background-padding': 2, 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'line-color': 'data(themeColor)', 'target-arrow-color': 'data(themeColor)', 'width': 2, 'opacity': 0.8}},
      {selector: 'edge:selected', style: {'line-color': '#f0883e', 'target-arrow-color': '#f0883e', 'width': 3}},
      {selector: '.faded', style: {'opacity': 0.08}},
      {selector: ':selected', style: {'border-width': 3, 'border-color': '#fff'}}
    ],
    layout: {name: 'cose', animate: false, idealEdgeLength: 90, nodeRepulsion: 12000, gravity: 0.8}
  });
  cy.on('tap', 'node', event => showNode(event.target.data()));
  cy.on('tap', 'edge', event => showEdge(event.target.data()));
  renderThemeLegend();
}

async function showGraph(graphId, historyMode = 'none') {
  const version = ++loadVersion;
  graphLoading = true;
  byId('graphSelect').disabled = true;
  byId('addButton').disabled = true;
  byId('classifyButton').disabled = true;
  byId('resetGraphButton').disabled = true;
  try {
    const next = await fetchJson(`/api/graphs/${encodeURIComponent(graphId)}`);
    if (version !== loadVersion) return;
    graph = next;
    domains = graph.nodes.filter(node => node.type === 'domain');
    activeGraphId = graph.id;
    byId('graphSelect').value = graph.id;
    byId('graphTitle').textContent = graph.title;
    document.title = `Concept Graph — ${graph.title}`;
    byId('search').value = '';
    byId('term').value = '';
    byId('desc').value = '';
    byId('ctype').value = 'concept';
    byId('layer').value = graph.id === defaultGraphId ? 'Custom' : '';
    byId('edgeRelation').value = '';
    byId('edgeAddStatus').textContent = '';
    byId('resetStatus').textContent = '';
    byId('newGraphPanel').hidden = true;
    byId('nodeEditor').hidden = true;
    byId('edgeEditor').hidden = true;
    selectedNodeId = null;
    selectedEdgeId = null;
    suggestedExistingNodeId = null;
    suggestedDuplicateNodeId = null;
    refreshConnectButton();
    populateControls();
    const introduction = graph.nodes.length
      ? graph.description
      : `${graph.description} Add your first concept to begin.`.trim();
    showMessage(graph.title, introduction);
    renderGraph();
    if (historyMode !== 'none') {
      const url = new URL(window.location.href);
      url.searchParams.set('graph', graph.id);
      window.history[`${historyMode}State`]({}, '', url);
    }
    return true;
  } catch (error) {
    if (version !== loadVersion) return;
    byId('graphSelect').value = activeGraphId || '';
    showMessage('Could not load graph', error.message);
    return false;
  } finally {
    if (version === loadVersion) {
      graphLoading = false;
      byId('graphSelect').disabled = false;
      refreshAddButton();
      byId('classifyButton').disabled = !activeGraphId;
      byId('resetGraphButton').disabled = !activeGraphId;
    }
  }
}

function fitGraph() {
  if (cy) cy.fit(undefined, 30);
}

function searchGraph() {
  if (!cy) return;
  const query = byId('search').value.toLowerCase();
  cy.elements().removeClass('faded');
  if (!query) return;
  cy.nodes().forEach(node => {
    const data = node.data();
    if (!(data.label || '').toLowerCase().includes(query)
        && !(data.description || '').toLowerCase().includes(query)) {
      node.addClass('faded');
    }
  });
}

function filterGraph() {
  if (!cy) return;
  const id = byId('filter').value;
  cy.elements().removeClass('faded');
  if (!id) return;
  const root = cy.getElementById(id);
  const keep = root.union(root.successors());
  cy.elements().difference(keep).addClass('faded');
  cy.fit(keep, 40);
}

async function classify() {
  if (graphLoading || !activeGraphId) return;
  const graphId = activeGraphId;
  const term = byId('term').value;
  const description = byId('desc').value;
  byId('classifyButton').disabled = true;
  try {
    const result = await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/classify`,
      jsonOptions('POST', {term, description})
    );
    if (graphId !== activeGraphId || term !== byId('term').value
        || description !== byId('desc').value) return;
    if ([...byId('parent').options].some(option => option.value === result.parent)) {
      byId('parent').value = result.parent;
    }
    if (result.parent === null) byId('parent').value = '';
    byId('parentRelation').disabled = !byId('parent').value;
    byId('parentRelation').value = result.relation || 'contains';
    if (result.type) byId('ctype').value = result.type;
    if (typeof result.layer === 'string') byId('layer').value = result.layer;
    byId('suggestion').textContent = result.reason || 'Placement suggested.';
    suggestedDuplicateNodeId = result.existing_node || null;
    suggestedExistingNodeId = result.existing_node && !result.relationship_exists
      ? result.existing_node : null;
    refreshConnectButton();
    refreshAddButton();
  } catch (error) {
    if (graphId === activeGraphId && term === byId('term').value
        && description === byId('desc').value) byId('suggestion').textContent = error.message;
  } finally {
    byId('classifyButton').disabled = graphLoading || !activeGraphId;
  }
}

async function connectSuggestedExisting() {
  if (graphLoading || !activeGraphId || !suggestedExistingNodeId) return;
  const graphId = activeGraphId;
  const payload = {
    source: byId('parent').value,
    target: suggestedExistingNodeId,
    relation: byId('parentRelation').value
  };
  byId('connectSuggestionButton').disabled = true;
  try {
    const created = await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/edges`, jsonOptions('POST', payload)
    );
    if (graphId === activeGraphId && await showGraph(graphId)) showEdge(created.edge);
  } catch (error) {
    if (graphId === activeGraphId) byId('suggestion').textContent = error.message;
  } finally {
    refreshConnectButton();
  }
}

async function resetGraph() {
  if (graphLoading || !activeGraphId) return;
  const graphId = activeGraphId;
  const message = `Reset "${graph.title}" for a new class? This replaces ${graph.nodes.length} concepts and ${graph.edges.length} relationships with its starter state (or an empty custom graph). A backup is saved first.`;
  if (!window.confirm(message)) return;
  byId('resetGraphButton').disabled = true;
  try {
    const result = await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/reset`, {method: 'POST'}
    );
    if (graphId === activeGraphId && await showGraph(graphId)) {
      byId('resetStatus').textContent = `Reset complete. Previous version saved to ${result.backup}`;
    }
  } catch (error) {
    if (graphId === activeGraphId) byId('resetStatus').textContent = error.message;
  } finally {
    byId('resetGraphButton').disabled = graphLoading || !activeGraphId;
  }
}

async function addNode() {
  if (graphLoading || !activeGraphId) return;
  const graphId = activeGraphId;
  const payload = {
    label: byId('term').value,
    description: byId('desc').value,
    parent: byId('parent').value,
    relation: byId('parentRelation').value,
    type: byId('ctype').value,
    layer: byId('layer').value
  };
  byId('addButton').disabled = true;
  try {
    const result = await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/nodes`, jsonOptions('POST', payload)
    );
    if (graphId === activeGraphId && await showGraph(graphId)) {
      showNode(graph.nodes.find(node => node.id === result.id));
    }
  } catch (error) {
    if (graphId === activeGraphId) byId('suggestion').textContent = error.message;
  } finally {
    refreshAddButton();
  }
}

async function refreshGraphList() {
  const result = await fetchJson('/api/graphs');
  if (!Array.isArray(result.graphs) || result.graphs.length === 0) {
    throw new Error('No graphs are available.');
  }
  availableGraphs = result.graphs;
  const selector = byId('graphSelect');
  selector.replaceChildren();
  for (const item of availableGraphs) selector.add(new Option(item.title, item.id));
  if (activeGraphId) selector.value = activeGraphId;
}

async function createGraph() {
  const title = byId('newGraphTitle').value;
  const id = byId('newGraphId').value.trim();
  const payload = {title, description: byId('newGraphDescription').value};
  if (id) payload.id = id;
  byId('createGraphButton').disabled = true;
  try {
    const created = await fetchJson('/api/graphs', jsonOptions('POST', payload));
    await refreshGraphList();
    await showGraph(created.id, 'push');
  } catch (error) {
    byId('newGraphStatus').textContent = error.message;
  } finally {
    byId('createGraphButton').disabled = false;
  }
}

async function saveNode() {
  if (graphLoading || !selectedNodeId) return;
  const graphId = activeGraphId;
  const nodeId = selectedNodeId;
  const payload = {
    label: byId('editNodeLabel').value,
    type: byId('editNodeType').value,
    layer: byId('editNodeLayer').value,
    description: byId('editNodeDescription').value
  };
  byId('saveNodeButton').disabled = true;
  try {
    await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/nodes/${encodeURIComponent(nodeId)}`,
      jsonOptions('PATCH', payload)
    );
    if (graphId === activeGraphId && await showGraph(graphId)) {
      showNode(graph.nodes.find(node => node.id === nodeId));
    }
  } catch (error) {
    if (graphId === activeGraphId) byId('nodeEditStatus').textContent = error.message;
  } finally {
    byId('saveNodeButton').disabled = false;
  }
}

async function deleteNode() {
  if (graphLoading || !selectedNodeId) return;
  const graphId = activeGraphId;
  const nodeId = selectedNodeId;
  const node = graph.nodes.find(item => item.id === nodeId);
  const connected = graph.edges.filter(edge => edge.source === nodeId || edge.target === nodeId).length;
  if (!window.confirm(`Delete "${node.label}" and its ${connected} connected relationship(s)?`)) return;
  byId('deleteNodeButton').disabled = true;
  try {
    await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/nodes/${encodeURIComponent(nodeId)}`,
      {method: 'DELETE'}
    );
    if (graphId === activeGraphId) await showGraph(graphId);
  } catch (error) {
    if (graphId === activeGraphId) byId('nodeEditStatus').textContent = error.message;
  } finally {
    byId('deleteNodeButton').disabled = false;
  }
}

async function addRelationship() {
  if (graphLoading || !activeGraphId) return;
  const graphId = activeGraphId;
  const payload = {
    source: byId('edgeSource').value,
    target: byId('edgeTarget').value,
    relation: byId('edgeRelation').value
  };
  byId('addEdgeButton').disabled = true;
  try {
    const created = await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/edges`, jsonOptions('POST', payload)
    );
    if (graphId === activeGraphId && await showGraph(graphId)) showEdge(created.edge);
  } catch (error) {
    if (graphId === activeGraphId) byId('edgeAddStatus').textContent = error.message;
  } finally {
    byId('addEdgeButton').disabled = graphLoading || !graph || graph.nodes.length < 2;
  }
}

async function saveRelationship() {
  if (graphLoading || !selectedEdgeId) return;
  const graphId = activeGraphId;
  const edgeId = selectedEdgeId;
  const payload = {
    source: byId('editEdgeSource').value,
    target: byId('editEdgeTarget').value,
    relation: byId('editEdgeRelation').value
  };
  byId('saveEdgeButton').disabled = true;
  try {
    const updated = await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/edges/${encodeURIComponent(edgeId)}`,
      jsonOptions('PATCH', payload)
    );
    if (graphId === activeGraphId && await showGraph(graphId)) showEdge(updated.edge);
  } catch (error) {
    if (graphId === activeGraphId) byId('edgeEditStatus').textContent = error.message;
  } finally {
    byId('saveEdgeButton').disabled = false;
  }
}

async function deleteRelationship() {
  if (graphLoading || !selectedEdgeId) return;
  const graphId = activeGraphId;
  const edgeId = selectedEdgeId;
  const edge = graph.edges.find(item => item.id === edgeId);
  if (!window.confirm(`Delete the "${edge.relation}" relationship?`)) return;
  byId('deleteEdgeButton').disabled = true;
  try {
    await fetchJson(
      `/api/graphs/${encodeURIComponent(graphId)}/edges/${encodeURIComponent(edgeId)}`,
      {method: 'DELETE'}
    );
    if (graphId === activeGraphId) await showGraph(graphId);
  } catch (error) {
    if (graphId === activeGraphId) byId('edgeEditStatus').textContent = error.message;
  } finally {
    byId('deleteEdgeButton').disabled = false;
  }
}

async function initialize() {
  byId('graphSelect').addEventListener('change', event => showGraph(event.target.value, 'push'));
  byId('newGraphButton').addEventListener('click', () => {
    byId('newGraphPanel').hidden = false;
    byId('newGraphStatus').textContent = '';
    byId('newGraphTitle').focus();
  });
  byId('cancelGraphButton').addEventListener('click', () => {
    byId('newGraphPanel').hidden = true;
  });
  byId('createGraphButton').addEventListener('click', createGraph);
  byId('search').addEventListener('input', searchGraph);
  byId('filter').addEventListener('change', filterGraph);
  byId('fitButton').addEventListener('click', fitGraph);
  byId('classifyButton').addEventListener('click', classify);
  byId('connectSuggestionButton').addEventListener('click', connectSuggestedExisting);
  byId('resetGraphButton').addEventListener('click', resetGraph);
  for (const field of ['term', 'desc']) {
    byId(field).addEventListener('input', () => {
      suggestedExistingNodeId = null;
      suggestedDuplicateNodeId = null;
      refreshConnectButton();
      refreshAddButton();
      byId('suggestion').textContent = '';
    });
  }
  byId('parent').addEventListener('change', () => {
    byId('parentRelation').disabled = !byId('parent').value;
    if (!byId('layer').value && byId('parent').value) {
      byId('layer').value = graph.nodes.find(node => node.id === byId('parent').value)?.layer || '';
    }
    refreshConnectButton();
  });
  byId('parentRelation').addEventListener('input', refreshConnectButton);
  byId('addButton').addEventListener('click', addNode);
  byId('saveNodeButton').addEventListener('click', saveNode);
  byId('deleteNodeButton').addEventListener('click', deleteNode);
  byId('closeNodeButton').addEventListener('click', () => {
    byId('nodeEditor').hidden = true;
    selectedNodeId = null;
  });
  byId('addEdgeButton').addEventListener('click', addRelationship);
  byId('saveEdgeButton').addEventListener('click', saveRelationship);
  byId('deleteEdgeButton').addEventListener('click', deleteRelationship);
  byId('closeEdgeButton').addEventListener('click', () => {
    byId('edgeEditor').hidden = true;
    selectedEdgeId = null;
  });
  window.addEventListener('popstate', () => {
    if (availableGraphs.length) showGraph(chooseGraphId());
  });

  try {
    await refreshGraphList();
    await showGraph(chooseGraphId(), 'replace');
  } catch (error) {
    showMessage('Could not load graphs', error.message);
    byId('addButton').disabled = true;
    byId('classifyButton').disabled = true;
    byId('resetGraphButton').disabled = true;
  }
}

initialize();
