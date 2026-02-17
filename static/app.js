const API_BASE = 'http://localhost:8000';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadGoals();
    loadTodayTasks();
    loadStats();
    
    // Set up event listeners
    document.getElementById('goalForm').addEventListener('submit', createGoal);
    document.getElementById('taskForm').addEventListener('submit', createTask);
    
    // Set default date to today
    document.getElementById('taskDate').valueAsDate = new Date();
});

// Create a new goal
async function createGoal(e) {
    e.preventDefault();
    
    const title = document.getElementById('goalTitle').value;
    const description = document.getElementById('goalDescription').value;
    const targetDate = document.getElementById('goalTargetDate').value;
    
    const button = e.target.querySelector('button');
    button.disabled = true;
    button.textContent = 'Creating...';
    
    try {
        const response = await fetch(`${API_BASE}/goals`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                target_date: targetDate ? new Date(targetDate).toISOString() : null
            })
        });
        
        if (response.ok) {
            const goal = await response.json();
            showMessage('Goal created successfully!', 'success');
            document.getElementById('goalForm').reset();
            loadGoals();
            
            // Ask if user wants to generate roadmap
            if (confirm('Goal created! Would you like to generate an AI roadmap now?')) {
                // Redirect to roadmap page
                window.location.href = `/roadmap?goalId=${goal.id}`;
            }
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

// Load all goals
async function loadGoals() {
    try {
        const response = await fetch(`${API_BASE}/goals`);
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
                    <button class="delete-goal-btn" data-goal-id="${goal.id}" title="Delete goal">
                        <span>✕</span>
                    </button>
                </div>
                <p>${goal.description || 'No description'}</p>
                <p><strong>Target:</strong> ${goal.target_date ? new Date(goal.target_date).toLocaleDateString() : 'No date set'}</p>
                <div class="goal-item-footer">
                    <span class="status ${goal.status}">${goal.status}</span>
                    <button class="view-roadmap-btn" data-goal-id="${goal.id}">View Roadmap →</button>
                </div>
            </div>
        `).join('');
        
        // Attach click handlers for view roadmap
        goalsList.querySelectorAll('.view-roadmap-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const goalId = btn.getAttribute('data-goal-id');
                window.location.href = `/roadmap?goalId=${goalId}`;
            });
        });
        
        // Attach click handlers for delete
        goalsList.querySelectorAll('.delete-goal-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const goalId = btn.getAttribute('data-goal-id');
                deleteGoal(goalId);
            });
        });
    } catch (error) {
        console.error('Error loading goals:', error);
    }
}

// Load today's tasks
async function loadTodayTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks/today`);
        const data = await response.json();
        
        const tasksList = document.getElementById('tasksList');
        
        if (data.tasks.length === 0) {
            tasksList.innerHTML = '<p style="color: var(--text-secondary); text-align: center; width: 100%;">No tasks for today. Create a goal and approve a roadmap to get started!</p>';
            return;
        }

        // Show summary bar
        const rescheduledNote = data.rescheduled
            ? `<span class="summary-rescheduled">${data.rescheduled} carried over</span>`
            : '';
        const summaryHtml = `
            <div class="today-summary">
                <span class="summary-total">${data.total} tasks today</span>
                <span class="summary-done">${data.completed} done</span>
                <span class="summary-due">${data.due} remaining</span>
                ${rescheduledNote}
            </div>
        `;
        
        const tasksHtml = data.tasks.map(task => {
            const contextLabel = task.goal_title
                ? `<span class="task-context">${task.goal_title}${task.milestone_title ? ' · ' + task.milestone_title : ''}</span>`
                : '';
            const rescheduledBadge = task.rescheduled
                ? '<span class="task-rescheduled-badge">carried over</span>'
                : '';
            return `
                <div class="task-item ${task.status === 1 ? 'task-completed' : ''} ${task.rescheduled ? 'task-rescheduled' : ''}">
                    <input type="checkbox" 
                           class="task-checkbox" 
                           ${task.status === 1 ? 'checked' : ''} 
                           onchange="toggleTask(${task.id}, this.checked)">
                    <div class="task-content">
                        <div class="task-title" style="${task.status === 1 ? 'text-decoration: line-through; opacity: 0.6;' : ''}">
                            ${task.title} ${rescheduledBadge}
                        </div>
                        ${task.description ? `<div class="task-description">${task.description}</div>` : ''}
                        ${contextLabel}
                    </div>
                    <span class="task-priority priority-${task.priority}">P${task.priority}</span>
                </div>
            `;
        }).join('');
        
        tasksList.innerHTML = summaryHtml + tasksHtml;
    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

// View goal - redirect to roadmap page
function viewGoal(goalId) {
    window.location.href = `/roadmap?goalId=${goalId}`;
}

// Delete a goal
async function deleteGoal(goalId) {
    if (!confirm('Are you sure you want to delete this goal? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/goals/${goalId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showMessage('Goal deleted successfully!', 'success');
            loadGoals();
            loadStats();
        } else {
            throw new Error('Failed to delete goal');
        }
    } catch (error) {
        showMessage('Error deleting goal: ' + error.message, 'error');
    }
}

// Create a new task
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
        const response = await fetch(`${API_BASE}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                category: 'daily',
                priority: parseInt(priority),
                scheduled_date: scheduledDate ? new Date(scheduledDate).toISOString() : new Date().toISOString()
            })
        });
        
        if (response.ok) {
            showMessage('Task created successfully!', 'success');
            document.getElementById('taskForm').reset();
            document.getElementById('taskDate').valueAsDate = new Date();
            loadTodayTasks();
            loadStats();
        } else {
            throw new Error('Failed to create task');
        }
    } catch (error) {
        showMessage('Error creating task: ' + error.message, 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Create Task';
    }
}

// Toggle task completion
async function toggleTask(taskId, isCompleted) {
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: isCompleted ? 1 : 0,
                reason: isCompleted ? 'Completed by user' : 'Marked as incomplete'
            })
        });
        
        if (response.ok) {
            loadTodayTasks();
            loadStats();
        }
    } catch (error) {
        console.error('Error updating task:', error);
    }
}

// Load statistics
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats/overview`);
        const stats = await response.json();
        
        document.getElementById('statsContent').innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">${stats.goals.active}</div>
                    <div class="stat-label">Active Goals</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.tasks.total}</div>
                    <div class="stat-label">Total Tasks</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.tasks.completed}</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.tasks.completion_rate}%</div>
                    <div class="stat-label">Success Rate</div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Show message
function showMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => messageDiv.remove(), 300);
    }, 3000);
}