let goalId = null;
let roadmapId = null;
let phases = [];
let currentPhaseIndex = 0;

async function api(url, options = {}) {
    options.headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    options.credentials = 'same-origin';
    const res = await fetch(url, options);
    if (res.status === 401) { window.location.href = '/'; throw new Error('Session expired'); }
    return res;
}

const urlParams = new URLSearchParams(window.location.search);
goalId = urlParams.get('goalId');

document.addEventListener('DOMContentLoaded', async () => {
    console.log('[roadmap] DOMContentLoaded, goalId=', goalId);
    if (!goalId) { alert('No goal specified!'); window.location.href = '/'; return; }
    await loadGoalDetails();
    await generateOrLoadRoadmap();
});

async function loadGoalDetails() {
    try {
        console.log('[roadmap] loadGoalDetails: fetching goal', goalId);
        const response = await api(`/goals/${goalId}`);
        const goal = await response.json();
        console.log('[roadmap] loadGoalDetails: goal loaded', goal.title);
        document.getElementById('goalName').textContent = goal.title;
        document.getElementById('goalTitle').textContent = goal.title;
        if (goal.target_date) {
            document.getElementById('goalDeadline').textContent = new Date(goal.target_date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
        } else {
            document.getElementById('goalDeadline').textContent = 'No deadline set';
        }
    } catch (error) {
        console.error('[roadmap] loadGoalDetails failed:', error);
    }
}

async function generateOrLoadRoadmap() {
    console.log('[roadmap] generateOrLoadRoadmap: start');
    const generatingEl = document.getElementById('generatingState');
    generatingEl.style.display = '';
    generatingEl.innerHTML = '<div class="spinner"></div><div class="generating-text">🤖 We are crafting your roadmap...</div><div class="generating-subtext">Analyzing your goal and creating a personalized journey</div>';
    document.getElementById('journeyContainer').style.display = 'none';

    try {
        let roadmap;
        let needsGeneration = true;

        try {
            console.log('[roadmap] GET /goals/' + goalId + '/roadmap');
            const response = await api(`/goals/${goalId}/roadmap`);
            if (response.ok) {
                roadmap = await response.json();
                console.log('[roadmap] GET roadmap ok, roadmap.id=', roadmap?.id);
                if (roadmap.phases) {
                    try {
                        const p = JSON.parse(roadmap.phases);
                        if (Array.isArray(p) && p.length > 0) {
                            needsGeneration = false;
                            console.log('[roadmap] existing phases found, skip generation, phases=', p.length);
                        }
                    } catch (e) {}
                }
            } else {
                console.log('[roadmap] GET roadmap not ok, status=', response.status);
                await response.text().catch(() => {});
            }
        } catch (e) {
            console.log('[roadmap] GET roadmap threw', e?.message || e);
        }

        if (needsGeneration) {
            console.log('[roadmap] POST /goals/' + goalId + '/roadmap (generate)');
            let response = await api(`/goals/${goalId}/roadmap`, { method: 'POST' });
            if (!response.ok) {
                const errDetail = await response.json().catch(() => ({}));
                const msg = errDetail.detail || 'Failed to generate roadmap';
                console.warn('[roadmap] POST generate failed, reason:', msg, 'status=', response.status, '— retrying in 2.5s');
                await new Promise(r => setTimeout(r, 2500));
                console.log('[roadmap] POST retry /goals/' + goalId + '/roadmap');
                response = await api(`/goals/${goalId}/roadmap`, { method: 'POST' });
            }
            if (!response.ok) {
                const errDetail = await response.json().catch(() => ({}));
                const msg = errDetail.detail || 'Failed to generate roadmap';
                console.error('[roadmap] POST generate failed after retry:', msg, 'status=', response.status);
                throw new Error(msg);
            }
            roadmap = await response.json();
            console.log('[roadmap] POST generate ok, roadmap.id=', roadmap?.id);
        }

        roadmapId = roadmap.id;
        console.log('[roadmap] loadPhases, roadmapId=', roadmapId);
        loadPhases(roadmap);
    } catch (error) {
        console.error('[roadmap] generateOrLoadRoadmap error:', error?.message || error);
        document.getElementById('generatingState').innerHTML = `<div style="color: var(--error); padding: 40px;"><h2>Error generating roadmap</h2><p>${error.message}</p><button onclick="window.location.href='/'">Go Back</button> <button onclick="generateOrLoadRoadmap(); this.disabled=true;">Retry</button></div>`;
    }
}

function clean(text) {
    if (!text) return '';
    return text.replace(/```[a-z]*\n?/g, '').replace(/```/g, '').replace(/#{1,6}\s*/g, '').replace(/\*\*([^*]+)\*\*/g, '$1').replace(/\*([^*]+)\*/g, '$1').replace(/__([^_]+)__/g, '$1').replace(/_([^_]+)_/g, '$1').replace(/^[\-\*]\s+/g, '').replace(/^\d+\.\s+/g, '').trim();
}

function loadPhases(roadmap) {
    if (roadmap.phases) {
        try {
            const parsed = typeof roadmap.phases === 'string' ? JSON.parse(roadmap.phases) : roadmap.phases;
            if (Array.isArray(parsed) && parsed.length > 0) {
                phases = parsed.slice(0, 10).map(p => ({
                    title: clean(p.title || ''), timeline: clean(p.timeline || ''), goal: clean(p.goal || ''),
                    tasks: (p.tasks || []).map(t => clean(t)).filter(t => t.length > 0),
                    success_criteria: (p.success_criteria || []).map(c => clean(c)).filter(c => c.length > 0),
                }));
                renderUI();
                return;
            }
        } catch (e) { console.error('Failed to parse phases JSON:', e); }
    }
    phases = [{ title: 'Roadmap', timeline: '', goal: 'Could not load structured phases. Please go back and try again.', tasks: [], success_criteria: [] }];
    renderUI();
}

function renderUI() {
    document.getElementById('totalPhases').textContent = phases.length;
    document.getElementById('generatingState').style.display = 'none';
    document.getElementById('journeyContainer').style.display = 'block';
    showPhase(0);
}

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
        container.innerHTML = `<div class="phase-stop active"><div class="phase-content">
            <div class="phase-header-row"><span class="phase-badge">${index + 1}</span><h2>${phase.title}</h2></div>
            ${phase.timeline ? `<div class="phase-timeline"><span class="icon">⏱️</span> ${phase.timeline}</div>` : ''}
            ${phase.goal ? `<p class="phase-goal">${phase.goal}</p>` : ''}
            ${tasks.length > 0 ? `<div class="phase-section"><h3>Key Tasks</h3><ul>${tasks.map(t => `<li>${t}</li>`).join('')}</ul></div>` : ''}
            ${criteria.length > 0 ? `<div class="phase-section phase-success"><h3>Success Criteria</h3><ul>${criteria.map(c => `<li>${c}</li>`).join('')}</ul></div>` : ''}
        </div></div>`;
        container.classList.remove('phase-exit');
        container.classList.add('phase-enter');
    }, 200);

    document.getElementById('progressFill').style.width = `${((index + 1) / phases.length) * 100}%`;
    document.getElementById('currentPhase').textContent = index + 1;
    renderPhaseDots(index);
    document.getElementById('prevButton').disabled = index === 0;
    const nextButton = document.getElementById('nextButton');
    if (index === phases.length - 1) { nextButton.textContent = 'Finish Review →'; nextButton.onclick = showFinalReview; }
    else { nextButton.innerHTML = 'Next <span>→</span>'; nextButton.onclick = nextPhase; }
}

function renderPhaseDots(activeIndex) {
    const d = document.getElementById('phaseDots');
    if (!d) return;
    d.innerHTML = phases.map((_, i) => `<button class="phase-dot ${i === activeIndex ? 'active' : ''} ${i < activeIndex ? 'completed' : ''}" onclick="showPhase(${i})" title="Phase ${i + 1}">${i < activeIndex ? '✓' : i + 1}</button>`).join('');
}

function nextPhase() { if (currentPhaseIndex < phases.length - 1) showPhase(currentPhaseIndex + 1); }
function previousPhase() { if (currentPhaseIndex > 0) showPhase(currentPhaseIndex - 1); }
document.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight') nextPhase(); if (e.key === 'ArrowLeft') previousPhase(); });

function showFinalReview() {
    document.getElementById('journeyContainer').style.display = 'none';
    document.getElementById('finalReview').style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function approveRoadmap() {
    const approveBtn = document.querySelector('.approve-button');
    const changesBtn = document.querySelector('.changes-button');
    if (approveBtn) { approveBtn.disabled = true; approveBtn.innerHTML = '<span class="spinner-small"></span> Generating your daily tasks...'; }
    if (changesBtn) changesBtn.disabled = true;

    try {
        const response = await api(`/roadmaps/${roadmapId}/approve`, { method: 'PUT' });
        if (response.ok) {
            const result = await response.json();
            if (approveBtn) approveBtn.innerHTML = '✓ Done!';
            showMessage(`Roadmap approved! ${result.tasks_created || 0} daily tasks created across ${result.milestones_created || 0} milestones. Redirecting...`, 'success');
            setTimeout(() => { window.location.href = '/'; }, 2500);
        } else {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to approve roadmap');
        }
    } catch (error) {
        showMessage('Error approving roadmap: ' + error.message, 'error');
        if (approveBtn) { approveBtn.disabled = false; approveBtn.innerHTML = '✓ Approve Roadmap'; }
        if (changesBtn) changesBtn.disabled = false;
    }
}

function requestChanges() { document.getElementById('changesModal').style.display = 'flex'; document.getElementById('changesText').focus(); }
function closeChangesModal() { document.getElementById('changesModal').style.display = 'none'; document.getElementById('changesText').value = ''; }

async function submitChanges() {
    const feedback = document.getElementById('changesText').value.trim();
    if (!feedback) { alert('Please describe what changes you would like'); return; }
    closeChangesModal();
    document.getElementById('finalReview').style.display = 'none';
    document.getElementById('journeyContainer').style.display = 'none';
    document.getElementById('generatingState').style.display = 'block';
    document.getElementById('generatingState').innerHTML = `<div class="spinner"></div><div class="generating-text">🤖 Refining your roadmap...</div><div class="generating-subtext">Updating the plan based on your feedback</div>`;

    try {
        const response = await api(`/roadmaps/${roadmapId}/refine`, { method: 'POST', body: JSON.stringify({ feedback }) });
        if (response.ok) { loadPhases(await response.json()); showMessage('Roadmap updated!', 'success'); }
        else { throw new Error('Failed to refine roadmap'); }
    } catch (error) {
        showMessage('Error refining roadmap: ' + error.message, 'error');
        document.getElementById('generatingState').style.display = 'none';
        document.getElementById('finalReview').style.display = 'block';
    }
}

function showMessage(message, type) {
    const d = document.createElement('div');
    d.className = `message ${type}`;
    d.textContent = message;
    document.body.appendChild(d);
    setTimeout(() => { d.style.animation = 'slideOutRight 0.3s ease'; setTimeout(() => d.remove(), 300); }, 3000);
}
