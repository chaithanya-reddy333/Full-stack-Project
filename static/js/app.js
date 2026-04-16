// ============================================
// Automated Quiz Engine - Main JavaScript
// ============================================

// ---- Flash Message Auto-dismiss ----
document.addEventListener('DOMContentLoaded', function () {
  const alerts = document.querySelectorAll('.alert-custom');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity 0.5s ease';
      alert.style.opacity = '0';
      setTimeout(function () { alert.remove(); }, 500);
    }, 4000);
  });
});

// ---- Quiz Engine ----
(function () {
  const quizForm = document.getElementById('quizForm');
  if (!quizForm) return;

  const questions = document.querySelectorAll('.question-block');
  const totalQuestions = questions.length;
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  const submitBtn = document.getElementById('submitBtn');

  // Update progress bar whenever an option is selected
  function updateProgress() {
    let answered = 0;
    questions.forEach(function (q) {
      if (q.querySelector('input[type=radio]:checked')) answered++;
    });
    const pct = totalQuestions > 0 ? Math.round((answered / totalQuestions) * 100) : 0;
    if (progressFill) progressFill.style.width = pct + '%';
    if (progressText) progressText.textContent = answered + '/' + totalQuestions + ' answered';
    if (submitBtn) {
      submitBtn.disabled = answered < totalQuestions;
      submitBtn.style.opacity = answered < totalQuestions ? '0.5' : '1';
    }
  }

  // Highlight selected option
  document.querySelectorAll('.option-item').forEach(function (item) {
    item.addEventListener('click', function () {
      const radioInput = this.querySelector('input[type=radio]');
      if (!radioInput) return;
      radioInput.checked = true;

      // Deselect siblings
      const block = this.closest('.question-block');
      block.querySelectorAll('.option-item').forEach(function (opt) {
        opt.classList.remove('selected');
      });
      this.classList.add('selected');
      updateProgress();
    });
  });

  // Confirm before submit
  quizForm.addEventListener('submit', function (e) {
    const unanswered = [];
    questions.forEach(function (q, idx) {
      if (!q.querySelector('input[type=radio]:checked')) unanswered.push(idx + 1);
    });
    if (unanswered.length > 0) {
      e.preventDefault();
      showToast('Please answer all questions before submitting.', 'warning');
      return;
    }
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Submitting...';
  });

  updateProgress();
})();

// ---- Quiz Timer ----
(function () {
  const timerEl = document.getElementById('quizTimer');
  if (!timerEl) return;

  const totalSeconds = parseInt(timerEl.dataset.seconds || '600', 10);
  let remaining = totalSeconds;

  function formatTime(secs) {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return m + ':' + s;
  }

  function tick() {
    timerEl.querySelector('#timerDisplay').textContent = formatTime(remaining);

    if (remaining <= 60) {
      timerEl.classList.remove('warning');
      timerEl.classList.add('danger');
    } else if (remaining <= 120) {
      timerEl.classList.add('warning');
    }

    if (remaining <= 0) {
      clearInterval(timerInterval);
      showToast('Time is up! Submitting your quiz...', 'warning');
      setTimeout(function () {
        const form = document.getElementById('quizForm');
        if (form) form.submit();
      }, 1500);
      return;
    }
    remaining--;
  }

  tick();
  const timerInterval = setInterval(tick, 1000);
})();

// ---- Toast Notification ----
function showToast(message, type) {
  type = type || 'info';
  const container = document.getElementById('toastContainer') || createToastContainer();

  const toast = document.createElement('div');
  toast.className = 'alert-custom alert-' + type;
  toast.style.cssText = 'margin-bottom: 0.5rem; min-width: 280px;';

  const icons = { success: '✅', danger: '❌', warning: '⚠️', info: 'ℹ️' };
  toast.innerHTML = '<span>' + (icons[type] || 'ℹ️') + '</span><span>' + message + '</span>';
  container.appendChild(toast);

  setTimeout(function () {
    toast.style.transition = 'opacity 0.4s ease';
    toast.style.opacity = '0';
    setTimeout(function () { toast.remove(); }, 400);
  }, 3500);
}

function createToastContainer() {
  const div = document.createElement('div');
  div.id = 'toastContainer';
  div.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;';
  document.body.appendChild(div);
  return div;
}

// ---- Admin: Confirm Delete ----
document.querySelectorAll('[data-confirm]').forEach(function (btn) {
  btn.addEventListener('click', function (e) {
    if (!confirm(this.dataset.confirm)) e.preventDefault();
  });
});

// ---- Certificate Score Circle ---- 
(function () {
  const circle = document.getElementById('resultCircle');
  if (!circle) return;
  const score = parseFloat(circle.dataset.score || '0');
  const pct = Math.min(100, Math.max(0, score));
  const isPassed = circle.classList.contains('pass');
  const color = isPassed ? '#43C6AC' : '#e74c3c';
  const light = isPassed ? 'rgba(67,198,172,0.15)' : 'rgba(231,76,60,0.12)';
  circle.style.background = `conic-gradient(${color} ${pct * 3.6}deg, ${light} ${pct * 3.6}deg)`;
})();

// ---- Animated Number Counters ----
function animateCounter(el) {
  const target = parseInt(el.dataset.target || el.textContent, 10);
  if (isNaN(target)) return;
  let current = 0;
  const step = Math.ceil(target / 50);
  const interval = setInterval(function () {
    current = Math.min(current + step, target);
    el.textContent = current;
    if (current >= target) clearInterval(interval);
  }, 30);
}

document.querySelectorAll('[data-counter]').forEach(animateCounter);

// ---- Smooth Scroll for anchor links ----
document.querySelectorAll('a[href^="#"]').forEach(function (a) {
  a.addEventListener('click', function (e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ---- Leaderboard quiz filter ----
const quizFilterSelect = document.getElementById('quizFilter');
if (quizFilterSelect) {
  quizFilterSelect.addEventListener('change', function () {
    const selected = this.value;
    document.querySelectorAll('.leaderboard-item[data-quiz]').forEach(function (item) {
      if (selected === 'all' || item.dataset.quiz === selected) {
        item.style.display = '';
      } else {
        item.style.display = 'none';
      }
    });
  });
}
