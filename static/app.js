const API_BASE = 'http://localhost:8000';
let currentGoalId = null;
let currentRoadmapId = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadGoals();
    loadTodayTasks();
    loadStats();
    
    // Set up event listeners
    document.getElementById('goalForm').addEventListener('submit', createGoal);
    document.getElementById('taskForm').addEventListener('submit', createTask);
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
                await generateRoadmap(goal.id);
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
            goalsList.innerHTML = '<p style="color: #666; text-align: center;">No goals yet. Create your first goal!</p>';
            return;
        }
        
        goalsList.innerHTML = goals.map(goal => `
            <div class="goal-item" onclick="viewGoalDetails(${goal.id})">
                <h3>${goal.title}</h3>
                <p>${goal.description || 'No description'}</p>
                <p><strong>Target:</strong> ${goal.target_date ? new Date(goal.target_date).toLocaleDateString() : 'No date set'}</p>
                <span class="status ${goal.status}">${goal.status}</span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading goals:', error);
    }
}

// View goal details and generate roadmap
async function viewGoalDetails(goalId) {
    currentGoalId = goalId;
    
    try {
        // Load goal
        const goalResponse = await fetch(`${API_BASE}/goals/${goalId}`);
        const goal = await goalResponse.json();
        
        // Check if roadmap exists
        const roadmapDiv = document.getElementById('roadmapContent');
        roadmapDiv.innerHTML = '<div class="loading">Loading roadmap...</div>';
        
        // Try to load existing roadmap
        // Note: You might want to add an endpoint to get roadmap by goal_id
        // For now, we'll check if one exists and show generate button
        
        const hasRoadmap = false; // You'll need to implement this check
        
        if (!hasRoadmap) {
            roadmapDiv.innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <p style="color: #666; margin-bottom: 20px;">No roadmap generated yet for this goal.</p>
                    <button onclick="generateRoadmap(${goalId})" class="btn-secondary">
                        Generate AI Roadmap with Gemini
                    </button>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading goal details:', error);
    }
}

// Generate roadmap with AI
async function generateRoadmap(goalId) {
    const roadmapDiv = document.getElementById('roadmapContent');
    roadmapDiv.innerHTML = '<div class="loading">Gemini is generating your roadmap... This may take a moment</div>';
    
    try {
        const response = await fetch(`${API_BASE}/goals/${goalId}/roadmap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            const roadmap = await response.json();
            currentRoadmapId = roadmap.id;
            displayRoadmap(roadmap);
            showMessage('Roadmap generated successfully!', 'success');
        } else {
            throw new Error('Failed to generate roadmap');
        }
    } catch (error) {
        roadmapDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

// Display roadmap
function displayRoadmap(roadmap) {
    const roadmapDiv = document.getElementById('roadmapContent');
    roadmapDiv.innerHTML = `
        <div class="roadmap-content">${roadmap.roadmap_text}</div>
        <div style="margin-top: 20px; display: flex; gap: 10px;">
            <button onclick="approveRoadmap(${roadmap.id})" class="btn-success" style="flex: 1;">
                Approve Roadmap
            </button>
            <button onclick="refineRoadmap(${roadmap.id})" class="btn-secondary" style="flex: 1;">
                Request Changes
            </button>
        </div>
    `;
}

// Approve roadmap
async function approveRoadmap(roadmapId) {
    try {
        const response = await fetch(`${API_BASE}/roadmaps/${roadmapId}/approve`, {
            method: 'PUT'
        });
        
        if (response.ok) {
            showMessage('Roadmap approved! You can now start creating tasks.', 'success');
        }
    } catch (error) {
        showMessage('Error approving roadmap: ' + error.message, 'error');
    }
}

// Refine roadmap
async function refineRoadmap(roadmapId) {
    const feedback = prompt('What changes would you like to make to the roadmap?');
    if (!feedback) return;
    
    const roadmapDiv = document.getElementById('roadmapContent');
    roadmapDiv.innerHTML = '<div class="loading">Refining roadmap based on your feedback...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/roadmaps/${roadmapId}/refine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feedback })
        });
        
        if (response.ok) {
            const roadmap = await response.json();
            displayRoadmap(roadmap);
            showMessage('Roadmap updated!', 'success');
        }
    } catch (error) {
        showMessage('Error refining roadmap: ' + error.message, 'error');
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

// Load today's tasks
async function loadTodayTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks/today`);
        const data = await response.json();
        
        const tasksList = document.getElementById('tasksList');
        
        if (data.tasks.length === 0) {
            tasksList.innerHTML = '<p style="color: #666; text-align: center;">No tasks for today. Create some tasks!</p>';
            return;
        }
        
        tasksList.innerHTML = data.tasks.map(task => `
            <div class="task-item">
                <input type="checkbox" 
                       class="task-checkbox" 
                       ${task.status === 1 ? 'checked' : ''} 
                       onchange="toggleTask(${task.id}, this.checked)">
                <div class="task-content">
                    <div class="task-title" style="${task.status === 1 ? 'text-decoration: line-through; opacity: 0.6;' : ''}">
                        ${task.title}
                    </div>
                    <div class="task-description">${task.description || ''}</div>
                </div>
                <span class="task-priority priority-${task.priority}">P${task.priority}</span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading tasks:', error);
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
    messageDiv.className = type;
    messageDiv.textContent = message;
    messageDiv.style.cssText = 'position: fixed; top: 20px; right: 20px; padding: 15px 25px; border-radius: 8px; z-index: 1000; animation: slideIn 0.3s;';
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.style.animation = 'slideOut 0.3s';
        setTimeout(() => messageDiv.remove(), 300);
    }, 3000);
}

// Set default date to today
document.getElementById('taskDate').valueAsDate = new Date();