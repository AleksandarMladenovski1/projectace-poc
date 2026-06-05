const API = "/api/v1";
let token = localStorage.getItem("pa_token");
let user = JSON.parse(localStorage.getItem("pa_user") || "null");

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(API + path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function showApp() {
  $("login-screen").classList.add("hidden");
  $("app").classList.remove("hidden");
  $("user-label").textContent = `${user.name} (${user.role})`;
  if (user.role !== "ADMIN") $("nav-employees").classList.add("hidden");
  loadDashboard();
  loadProjects();
}

function showLogin() {
  $("login-screen").classList.remove("hidden");
  $("app").classList.add("hidden");
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("login-err").textContent = "";
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: $("email").value, password: $("password").value }),
    });
    token = data.access_token;
    user = data.user;
    localStorage.setItem("pa_token", token);
    localStorage.setItem("pa_user", JSON.stringify(user));
    showApp();
  } catch (err) {
    $("login-err").textContent = err.message;
  }
});

$("logout-btn").addEventListener("click", () => {
  token = null; user = null;
  localStorage.removeItem("pa_token");
  localStorage.removeItem("pa_user");
  showLogin();
});

document.querySelectorAll("[data-view]").forEach((el) => {
  el.addEventListener("click", () => {
    document.querySelectorAll("[data-view]").forEach((a) => a.classList.remove("active"));
    el.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    $(`view-${el.dataset.view}`).classList.remove("hidden");
    if (el.dataset.view === "dashboard") loadDashboard();
    if (el.dataset.view === "projects") loadProjects();
    if (el.dataset.view === "kanban" && $("project-select").value) loadBoard($("project-select").value);
    if (el.dataset.view === "employees") loadEmployees();
    if (el.dataset.view === "activity") loadActivity();
  });
});

async function loadDashboard() {
  const stats = await api("/dashboard/stats");
  const charts = await api("/dashboard/charts");
  $("stat-projects").textContent = stats.active_projects;
  $("stat-tasks").textContent = stats.total_tasks;
  $("stat-done").textContent = stats.completed_tasks;
  $("stat-overdue").textContent = stats.overdue_tasks;
  renderBarChart("chart-status", charts.by_status, ["#6366f1", "#f59e0b", "#22c55e"]);
  renderBarChart("chart-priority", charts.by_priority, ["#22c55e", "#6366f1", "#ef4444"]);
}

function renderBarChart(canvasId, data, colors) {
  const canvas = $(canvasId);
  const ctx = canvas.getContext("2d");
  const labels = Object.keys(data);
  const values = Object.values(data);
  const max = Math.max(...values, 1);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const w = canvas.width / labels.length;
  labels.forEach((lbl, i) => {
    const h = (values[i] / max) * (canvas.height - 30);
    ctx.fillStyle = colors[i % colors.length];
    ctx.fillRect(i * w + 10, canvas.height - h - 20, w - 20, h);
    ctx.fillStyle = "#8b9cb3";
    ctx.font = "11px sans-serif";
    ctx.fillText(lbl.replace("_", " "), i * w + 8, canvas.height - 4);
  });
}

async function loadProjects() {
  const projects = await api("/projects");
  const sel = $("project-select");
  sel.innerHTML = projects.map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
  $("projects-list").innerHTML = projects.map((p) =>
    `<tr><td>${p.name}</td><td>${p.status}</td><td>${p.deadline || "—"}</td>
     <td><button class="secondary" onclick="openBoard(${p.id})">Board</button></td></tr>`
  ).join("");
}

window.openBoard = (id) => {
  $("project-select").value = id;
  document.querySelector('[data-view="kanban"]').click();
  loadBoard(id);
};

let currentBoardProjectId = null;
let draggedCard = null;
let dragPreview = null;

function createTaskCard(t) {
  const card = document.createElement("div");
  card.className = "task-card" + (t.overdue ? " overdue" : "");
  card.draggable = true;
  card.dataset.id = t.id;
  card.innerHTML = `<strong>${t.title}</strong><br><span class="badge ${t.priority}">${t.priority}</span>
    <small>${t.assignee_name || "Unassigned"}</small>`;
  card.addEventListener("dragstart", (e) => {
    draggedCard = card;
    e.dataTransfer.setData("text/plain", String(t.id));
    e.dataTransfer.effectAllowed = "move";
    dragPreview = card.cloneNode(true);
    dragPreview.classList.add("task-card-drag-preview");
    dragPreview.style.width = `${card.offsetWidth}px`;
    document.body.appendChild(dragPreview);
    e.dataTransfer.setDragImage(dragPreview, e.offsetX, e.offsetY);
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", () => {
    dragPreview?.remove();
    dragPreview = null;
    card.classList.remove("dragging");
    draggedCard = null;
    document.querySelectorAll(".column-drop-target").forEach((el) => el.classList.remove("column-drop-target"));
  });
  return card;
}

function setupKanbanDropZones() {
  ["TODO", "IN_PROGRESS", "DONE"].forEach((status) => {
    const col = $(`col-${status}`);
    if (col.dataset.dndBound) return;
    col.dataset.dndBound = "1";
    const column = col.closest(".column");
    col.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      column.classList.add("column-drop-target");
    });
    col.addEventListener("dragleave", (e) => {
      if (!col.contains(e.relatedTarget)) column.classList.remove("column-drop-target");
    });
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      column.classList.remove("column-drop-target");
      const taskId = e.dataTransfer.getData("text/plain");
      if (!taskId || !currentBoardProjectId) return;
      const card = draggedCard || document.querySelector(`.task-card[data-id="${taskId}"]`);
      if (!card) return;
      const fromCol = card.parentElement;
      const fromStatus = fromCol?.id?.replace("col-", "");
      if (fromStatus === status) return;
      col.appendChild(card);
      try {
        await api(`/tasks/${taskId}/move`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        });
      } catch (err) {
        fromCol.appendChild(card);
        alert(err.message);
      }
    });
  });
}

$("project-select").addEventListener("change", () => {
  if ($("project-select").value) loadBoard($("project-select").value);
});

async function loadBoard(projectId) {
  currentBoardProjectId = projectId;
  setupKanbanDropZones();
  const board = await api(`/projects/${projectId}/board`);
  ["TODO", "IN_PROGRESS", "DONE"].forEach((status) => {
    const col = $(`col-${status}`);
    col.innerHTML = "";
    (board[status] || []).forEach((t) => col.appendChild(createTaskCard(t)));
  });
}

$("add-task-btn").addEventListener("click", async () => {
  const pid = $("project-select").value;
  const title = $("new-task-title").value.trim();
  if (!title) return;
  await api(`/projects/${pid}/tasks`, { method: "POST", body: JSON.stringify({ title }) });
  $("new-task-title").value = "";
  loadBoard(pid);
});

async function loadEmployees() {
  const rows = await api("/employees");
  $("employees-table").innerHTML = rows.map((e) =>
    `<tr><td>${e.name}</td><td>${e.email}</td><td>${e.role}</td><td>${e.department || "—"}</td></tr>`
  ).join("");
}

async function loadActivity() {
  const logs = await api("/activity");
  $("activity-list").innerHTML = logs.map((a) =>
    `<li>${a.created_at.slice(0, 16)} — ${a.message || a.action}</li>`
  ).join("");
}

if (token && user) showApp();
else showLogin();
