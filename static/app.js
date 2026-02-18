const API_BASE = '';

// ==================== SIMPLE FETCH WRAPPER ====================

async function api(url, options = {}) {
    options.headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    options.credentials = 'same-origin';
    const res = await fetch(url, options);
    if (res.status === 401) {
        showScreen('auth');
        return null;
    }
    return res;
}

// ==================== SCREEN MANAGEMENT ====================

function showScreen(name) {
    document.getElementById('authScreen').style.display = name === 'auth' ? '' : 'none';
    document.getElementById('appScreen').style.display = name === 'app' ? '' : 'none';
}

// ==================== AUTH UI ====================

async function handlePhoneLogin(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    btn.disabled = true;
    btn.textContent = 'Signing in...';
    try {
        const res = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ phone: document.getElementById('phoneInput').value }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Login failed');
        }
        await res.json();
        showScreen('app');
        bootstrap();
    } catch (err) {
        showMessage(err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Continue';
    }
}

async function handleLogout() {
    await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
    showScreen('auth');
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async () => {
    const res = await fetch('/auth/me', { credentials: 'same-origin' });
    if (res.ok) {
        await res.json();
        showScreen('app');
        bootstrap();
    } else {
        showScreen('auth');
    }
});

function bootstrap() {
    loadGoals();
    loadTodayTasks();
    loadStats();

    const goalForm = document.getElementById('goalForm');
    const taskForm = document.getElementById('taskForm');
    goalForm.onsubmit = createGoal;
    taskForm.onsubmit = createTask;
    document.getElementById('taskDate').valueAsDate = new Date();
}

// ==================== GOAL FUNCTIONS ====================

async function createGoal(e) {
    e.preventDefault();
    const title = document.getElementById('goalTitle').value;
    const description = document.getElementById('goalDescription').value;
    const targetDate = document.getElementById('goalTargetDate').value;
    const button = e.target.querySelector('button');
    button.disabled = true;
    button.textContent = 'Creating...';

    try {
        const response = await api('/goals', {
            method: 'POST',
            body: JSON.stringify({
                title,
                description,
                target_date: targetDate ? new Date(targetDate).toISOString() : null,
            }),
        });
        if (!response) return;

        if (response.ok) {
            const goal = await response.json();
            showMessage('Goal created! Generating your roadmap...', 'success');
            document.getElementById('goalForm').reset();
            setTimeout(() => { window.location.href = `/roadmap?goalId=${goal.id}`; }, 800);
        } else {
            throw new Error('Failed to create goal');
        }
    } catch (error) {
        showMessage('Error creating goal: ' + error.message, 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Create Goal';
    }
}

async function loadGoals() {
    try {
        const response = await api('/goals');
        if (!response) return;
        const goals = await response.json();
        const goalsList = document.getElementById('goalsList');

        if (goals.length === 0) {
            goalsList.innerHTML = '<p style="color: var(--text-secondary); text-align: center; width: 100%;">No goals yet. Create your first goal!</p>';
            return;
        }

        goalsList.innerHTML = goals.map(goal => `
            <div class="goal-item" data-goal-id="${goal.id}">
                <div class="goal-item-header">
                    <h3>${goal.title}</h3>
                    <button class="delete-goal-btn" data-goal-id="${goal.id}" title="Delete goal"><span>✕</span></button>
                </div>
                <p>${goal.description || 'No description'}</p>
                <p><strong>Target:</strong> ${goal.target_date ? new Date(goal.target_date).toLocaleDateString() : 'No date set'}</p>
                <div class="goal-item-footer">
                    <span class="status ${goal.status}">${goal.status}</span>
                    <button class="view-roadmap-btn" data-goal-id="${goal.id}">View Roadmap →</button>
                </div>
            </div>
        `).join('');

        goalsList.querySelectorAll('.view-roadmap-btn').forEach(btn => {
            btn.addEventListener('click', (e) => { e.stopPropagation(); window.location.href = `/roadmap?goalId=${btn.dataset.goalId}`; });
        });
        goalsList.querySelectorAll('.delete-goal-btn').forEach(btn => {
            btn.addEventListener('click', (e) => { e.stopPropagation(); deleteGoal(btn.dataset.goalId); });
        });
    } catch (error) {
        console.error('Error loading goals:', error);
    }
}

async function deleteGoal(goalId) {
    if (!confirm('Are you sure you want to delete this goal? This action cannot be undone.')) return;
    try {
        const response = await api(`/goals/${goalId}`, { method: 'DELETE' });
        if (!response) return;
        if (response.ok) { showMessage('Goal deleted successfully!', 'success'); loadGoals(); loadStats(); }
        else { throw new Error('Failed to delete goal'); }
    } catch (error) { showMessage('Error deleting goal: ' + error.message, 'error'); }
}

// ==================== TASK FUNCTIONS ====================

async function loadTodayTasks() {
    try {
        const response = await api('/tasks/today');
        if (!response) return;
        const data = await response.json();
        const tasksList = document.getElementById('tasksList');
        const summaryEl = document.getElementById('todaySummary');

        if (data.tasks.length === 0) {
            summaryEl.innerHTML = '';
            tasksList.innerHTML = '<p class="empty-state">No tasks for today. Create a goal and approve a roadmap to get started!</p>';
            return;
        }

        const rescheduledNote = data.rescheduled ? `<span class="summary-rescheduled">${data.rescheduled} carried over</span>` : '';
        summaryEl.innerHTML = `<span class="summary-done">${data.completed}/${data.total} done</span><span class="summary-due">${data.due} remaining</span>${rescheduledNote}`;

        const groups = {};
        const noGroup = [];
        data.tasks.forEach(task => {
            const key = task.milestone_title || null;
            if (key) { (groups[key] = groups[key] || []).push(task); } else { noGroup.push(task); }
        });

        let html = '';
        let num = 1;
        const renderTask = (task) => {
            const isDone = task.status === 1;
            const badge = task.rescheduled ? ' <span class="task-rescheduled-badge">carried over</span>' : '';
            const row = `<label class="checklist-row ${isDone ? 'done' : ''} ${task.rescheduled ? 'rescheduled' : ''}" for="task-${task.id}">
                <input type="checkbox" id="task-${task.id}" class="checklist-cb" ${isDone ? 'checked' : ''} onchange="toggleTask(${task.id}, this.checked)">
                <span class="checklist-num">${num}</span>
                <span class="checklist-text">${task.title}${badge}</span>
                <span class="task-priority priority-${task.priority}">P${task.priority}</span>
            </label>`;
            num++;
            return row;
        };

        for (const [milestone, tasks] of Object.entries(groups)) {
            html += `<div class="checklist-group"><div class="checklist-phase-header">${milestone}</div>${tasks.map(renderTask).join('')}</div>`;
        }
        if (noGroup.length) html += noGroup.map(renderTask).join('');
        tasksList.innerHTML = html;
    } catch (error) { console.error('Error loading tasks:', error); }
}

async function createTask(e) {
    e.preventDefault();
    const title = document.getElementById('taskTitle').value;
    const description = document.getElementById('taskDescription').value;
    const priority = document.getElementById('taskPriority').value;
    const scheduledDate = document.getElementById('taskDate').value;
    const button = e.target.querySelector('button');
    button.disabled = true;
    button.textContent = 'Creating...';

    try {
        const response = await api('/tasks', {
            method: 'POST',
            body: JSON.stringify({ title, description, category: 'daily', priority: parseInt(priority), scheduled_date: scheduledDate ? new Date(scheduledDate).toISOString() : new Date().toISOString() }),
        });
        if (!response) return;
        if (response.ok) {
            showMessage('Task created successfully!', 'success');
            document.getElementById('taskForm').reset();
            document.getElementById('taskDate').valueAsDate = new Date();
            loadTodayTasks();
            loadStats();
        } else { throw new Error('Failed to create task'); }
    } catch (error) { showMessage('Error creating task: ' + error.message, 'error'); }
    finally { button.disabled = false; button.textContent = 'Create Task'; }
}

async function toggleTask(taskId, isCompleted) {
    try {
        const response = await api(`/tasks/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: isCompleted ? 1 : 0, reason: isCompleted ? 'Completed by user' : 'Marked as incomplete' }),
        });
        if (response && response.ok) { loadTodayTasks(); loadStats(); }
    } catch (error) { console.error('Error updating task:', error); }
}

// ==================== STATS ====================

async function loadStats() {
    try {
        const response = await api('/stats/overview');
        if (!response) return;
        const stats = await response.json();
        document.getElementById('statsContent').innerHTML = `
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-number">${stats.goals.active}</div><div class="stat-label">Active Goals</div></div>
                <div class="stat-card"><div class="stat-number">${stats.tasks.total}</div><div class="stat-label">Total Tasks</div></div>
                <div class="stat-card"><div class="stat-number">${stats.tasks.completed}</div><div class="stat-label">Completed</div></div>
                <div class="stat-card"><div class="stat-number">${stats.tasks.completion_rate}%</div><div class="stat-label">Success Rate</div></div>
            </div>`;
    } catch (error) { console.error('Error loading stats:', error); }
}

// ==================== UTILITIES ====================

function showMessage(message, type) {
    const d = document.createElement('div');
    d.className = `message ${type}`;
    d.textContent = message;
    document.body.appendChild(d);
    setTimeout(() => { d.style.animation = 'slideOutRight 0.3s ease'; setTimeout(() => d.remove(), 300); }, 3000);
}
