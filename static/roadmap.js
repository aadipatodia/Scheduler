const API_BASE = 'http://localhost:8000';
let goalId = null;
let roadmapId = null;
let phases = [];
let currentPhaseIndex = 0;

const urlParams = new URLSearchParams(window.location.search);
goalId = urlParams.get('goalId');

document.addEventListener('DOMContentLoaded', async () => {
    if (!goalId) {
        alert('No goal specified!');
        window.location.href = '/';
        return;
    }
    await loadGoalDetails();
    await generateOrLoadRoadmap();
});

async function loadGoalDetails() {
    try {
        const response = await fetch(`${API_BASE}/goals/${goalId}`);
        const goal = await response.json();
        document.getElementById('goalName').textContent = goal.title;
        document.getElementById('goalTitle').textContent = goal.title;
        if (goal.target_date) {
            const date = new Date(goal.target_date);
            document.getElementById('goalDeadline').textContent = date.toLocaleDateString('en-US', {
                year: 'numeric', month: 'long', day: 'numeric'
            });
        } else {
            document.getElementById('goalDeadline').textContent = 'No deadline set';
        }
    } catch (error) {
        console.error('Error loading goal:', error);
    }
}

async function generateOrLoadRoadmap() {
    try {
        let roadmap;
        let needsGeneration = true;

        // Try loading existing roadmap
        try {
            const response = await fetch(`${API_BASE}/goals/${goalId}/roadmap`);
            if (response.ok) {
                roadmap = await response.json();
                // Check if it has structured phases JSON
                if (roadmap.phases) {
                    try {
                        const parsed = JSON.parse(roadmap.phases);
                        if (Array.isArray(parsed) && parsed.length > 0) {
                            needsGeneration = false;
                        }
                    } catch (e) {}
                }
            }
        } catch (e) {}

        // Generate (or re-generate) if no valid structured phases
        if (needsGeneration) {
            const response = await fetch(`${API_BASE}/goals/${goalId}/roadmap`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) throw new Error('Failed to generate roadmap');
            roadmap = await response.json();
        }

        roadmapId = roadmap.id;
        loadPhases(roadmap);

    } catch (error) {
        console.error('Error with roadmap:', error);
        document.getElementById('generatingState').innerHTML = `
            <div style="color: var(--error); padding: 40px;">
                <h2>Error generating roadmap</h2>
                <p>${error.message}</p>
                <button onclick="window.location.href='/'">Go Back</button>
            </div>
        `;
    }
}

// Strip markdown formatting from a string
function clean(text) {
    if (!text) return '';
    return text
        .replace(/```[a-z]*\n?/g, '')
        .replace(/```/g, '')
        .replace(/#{1,6}\s*/g, '')
        .replace(/\*\*([^*]+)\*\*/g, '$1')
        .replace(/\*([^*]+)\*/g, '$1')
        .replace(/__([^_]+)__/g, '$1')
        .replace(/_([^_]+)_/g, '$1')
        .replace(/^[\-\*]\s+/g, '')
        .replace(/^\d+\.\s+/g, '')
        .trim();
}

// Load phases from the API response - structured JSON, no regex parsing
function loadPhases(roadmap) {
    if (roadmap.phases) {
        try {
            const parsed = typeof roadmap.phases === 'string' ? JSON.parse(roadmap.phases) : roadmap.phases;
            if (Array.isArray(parsed) && parsed.length > 0) {
                phases = parsed.slice(0, 10).map(p => ({
                    title: clean(p.title || ''),
                    timeline: clean(p.timeline || ''),
                    goal: clean(p.goal || ''),
                    tasks: (p.tasks || []).map(t => clean(t)).filter(t => t.length > 0),
                    success_criteria: (p.success_criteria || []).map(c => clean(c)).filter(c => c.length > 0)
                }));
                renderUI();
                return;
            }
        } catch (e) {
            console.error('Failed to parse phases JSON:', e);
        }
    }

    // This should rarely happen now since we auto-regenerate, but just in case
    phases = [{
        title: 'Roadmap',
        timeline: '',
        goal: 'Could not load structured phases. Please go back and try again.',
        tasks: [],
        success_criteria: []
    }];
    renderUI();
}

function renderUI() {
    document.getElementById('totalPhases').textContent = phases.length;
    document.getElementById('generatingState').style.display = 'none';
    document.getElementById('journeyContainer').style.display = 'block';
    showPhase(0);
}

// Render a single phase
function showPhase(index) {
    currentPhaseIndex = index;
    const phase = phases[index];
    if (!phase) return;

    const container = document.getElementById('phasesContainer');

    container.classList.remove('phase-enter');
    container.classList.add('phase-exit');

    setTimeout(() => {
        const tasks = phase.tasks || [];
        const criteria = phase.success_criteria || [];

        container.innerHTML = `
            <div class="phase-stop active">
                <div class="phase-content">
                    <div class="phase-header-row">
                        <span class="phase-badge">${index + 1}</span>
                        <h2>${phase.title}</h2>
                    </div>
                    ${phase.timeline ? `
                        <div class="phase-timeline">
                            <span class="icon">⏱️</span> ${phase.timeline}
                        </div>
                    ` : ''}
                    ${phase.goal ? `<p class="phase-goal">${phase.goal}</p>` : ''}
                    ${tasks.length > 0 ? `
                        <div class="phase-section">
                            <h3>Key Tasks</h3>
                            <ul>${tasks.map(t => `<li>${t}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                    ${criteria.length > 0 ? `
                        <div class="phase-section phase-success">
                            <h3>Success Criteria</h3>
                            <ul>${criteria.map(c => `<li>${c}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;

        container.classList.remove('phase-exit');
        container.classList.add('phase-enter');
    }, 200);

    // Progress
    const progress = ((index + 1) / phases.length) * 100;
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('currentPhase').textContent = index + 1;

    // Dots
    renderPhaseDots(index);

    // Buttons
    document.getElementById('prevButton').disabled = index === 0;
    const nextButton = document.getElementById('nextButton');
    if (index === phases.length - 1) {
        nextButton.textContent = 'Finish Review →';
        nextButton.onclick = showFinalReview;
    } else {
        nextButton.innerHTML = 'Next <span>→</span>';
        nextButton.onclick = nextPhase;
    }
}

function renderPhaseDots(activeIndex) {
    const dotsContainer = document.getElementById('phaseDots');
    if (!dotsContainer) return;
    dotsContainer.innerHTML = phases.map((_, i) => `
        <button class="phase-dot ${i === activeIndex ? 'active' : ''} ${i < activeIndex ? 'completed' : ''}"
                onclick="showPhase(${i})"
                title="Phase ${i + 1}">
            ${i < activeIndex ? '✓' : i + 1}
        </button>
    `).join('');
}

function nextPhase() {
    if (currentPhaseIndex < phases.length - 1) showPhase(currentPhaseIndex + 1);
}

function previousPhase() {
    if (currentPhaseIndex > 0) showPhase(currentPhaseIndex - 1);
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') nextPhase();
    if (e.key === 'ArrowLeft') previousPhase();
});

function showFinalReview() {
    document.getElementById('journeyContainer').style.display = 'none';
    document.getElementById('finalReview').style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function approveRoadmap() {
    const approveBtn = document.querySelector('.approve-button');
    const changesBtn = document.querySelector('.changes-button');
    if (approveBtn) {
        approveBtn.disabled = true;
        approveBtn.innerHTML = '<span class="spinner-small"></span> Generating your daily tasks...';
    }
    if (changesBtn) changesBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/roadmaps/${roadmapId}/approve`, { method: 'PUT' });
        if (response.ok) {
            const result = await response.json();
            const taskCount = result.tasks_created || 0;
            const milestoneCount = result.milestones_created || 0;
            if (approveBtn) {
                approveBtn.innerHTML = '✓ Done!';
            }
            showMessage(
                `Roadmap approved! ${taskCount} daily tasks created across ${milestoneCount} milestones. Redirecting...`,
                'success'
            );
            setTimeout(() => { window.location.href = '/'; }, 2500);
        } else {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to approve roadmap');
        }
    } catch (error) {
        showMessage('Error approving roadmap: ' + error.message, 'error');
        if (approveBtn) {
            approveBtn.disabled = false;
            approveBtn.innerHTML = '✓ Approve Roadmap';
        }
        if (changesBtn) changesBtn.disabled = false;
    }
}

function requestChanges() {
    document.getElementById('changesModal').style.display = 'flex';
    document.getElementById('changesText').focus();
}

function closeChangesModal() {
    document.getElementById('changesModal').style.display = 'none';
    document.getElementById('changesText').value = '';
}

async function submitChanges() {
    const feedback = document.getElementById('changesText').value.trim();
    if (!feedback) { alert('Please describe what changes you would like'); return; }

    closeChangesModal();
    document.getElementById('finalReview').style.display = 'none';
    document.getElementById('journeyContainer').style.display = 'none';
    document.getElementById('generatingState').style.display = 'block';
    document.getElementById('generatingState').innerHTML = `
        <div class="spinner"></div>
        <div class="generating-text">🤖 Refining your roadmap...</div>
        <div class="generating-subtext">Gemini is updating the plan based on your feedback</div>
    `;

    try {
        const response = await fetch(`${API_BASE}/roadmaps/${roadmapId}/refine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feedback })
        });
        if (response.ok) {
            const roadmap = await response.json();
            loadPhases(roadmap);
            showMessage('Roadmap updated!', 'success');
        } else {
            throw new Error('Failed to refine roadmap');
        }
    } catch (error) {
        showMessage('Error refining roadmap: ' + error.message, 'error');
        document.getElementById('generatingState').style.display = 'none';
        document.getElementById('finalReview').style.display = 'block';
    }
}

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
