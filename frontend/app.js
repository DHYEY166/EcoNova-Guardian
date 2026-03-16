/**
 * EcoNova Guardian – frontend
 * Live camera: auto-classifies in real time every few seconds. Camera keeps running.
 */
const API_BASE = (window.location.protocol === 'file:' || window.location.hostname === 'localhost')
  ? 'http://localhost:8000'
  : '';

const AUTO_CLASSIFY_INTERVAL_MS = 700;  // Cheap local checks can run faster without increasing Bedrock calls
const THANK_YOU_DURATION_MS = 2500;    // Show thank you then resume auto-classify
const ROI_WIDTH_RATIO = 0.4;           // Larger crop for easier item placement
const ROI_HEIGHT_RATIO = 0.4;
const DEFAULT_ROI_CENTER_X = 0.5;
const DEFAULT_ROI_CENTER_Y = 0.72;
const SIGNATURE_SIZE = 24;
const SCENE_CHANGE_THRESHOLD = 10;
const SCENE_RESET_THRESHOLD = 6;
const OBJECT_SWAP_THRESHOLD = 10;
const RESET_STABLE_TICKS_REQUIRED = 2;
const MIN_CLASSIFY_GAP_MS = 3500;
const CHANGE_TICKS_REQUIRED = 3;
const CLASSIFY_HINT = [
  'Classify only the single nearest waste item physically held inside the guide box.',
  'Ignore human body parts and clothing (shirt, skin, face, hands).',
  'Ignore background objects, floors, tables, and anything outside the guide box.',
  'If no clear waste item is visible or being actively held in the box, respond with category "none" and item_name "nothing".',
].join(' ');

const cameraStart = document.getElementById('cameraStart');
const startCameraBtn = document.getElementById('startCameraBtn');
const cameraLive = document.getElementById('cameraLive');
const cameraVideo = document.getElementById('cameraVideo');
const cameraRoi = document.querySelector('.camera-roi');
const lockBinZoneBtn = document.getElementById('lockBinZoneBtn');
const roiHint = document.getElementById('roiHint');
const pauseResumeBtn = document.getElementById('pauseResumeBtn');
const stopCameraBtn = document.getElementById('stopCameraBtn');
const resultSection = document.getElementById('resultSection');
const resultLoading = document.getElementById('resultLoading');
const resultContent = document.getElementById('resultContent');
const binViz = document.getElementById('binViz');
const categoryPill = document.getElementById('categoryPill');
const itemName = document.getElementById('itemName');
const confidenceText = document.getElementById('confidenceText');
const reasoning = document.getElementById('reasoning');
const tips = document.getElementById('tips');
const clarificationBox = document.getElementById('clarificationBox');
const clarificationQuestion = document.getElementById('clarificationQuestion');
const clarificationOptions = document.getElementById('clarificationOptions');
const feedbackBox = document.getElementById('feedbackBox');
const feedbackCorrect = document.getElementById('feedbackCorrect');
const thankYouMsg = document.getElementById('thankYouMsg');
const statsLink = document.getElementById('statsLink');
const statsModal = document.getElementById('statsModal');
const statsBody = document.getElementById('statsBody');
const closeStatsBtn = document.getElementById('closeStatsBtn');

let currentStream = null;
let lastResult = null;
let autoClassifyTimer = null;
let classifyInFlight = false;
let paused = false;
let selectingBinZone = false;
let roiCenterX = DEFAULT_ROI_CENTER_X;
let roiCenterY = DEFAULT_ROI_CENTER_Y;
let baselineSignature = null;
let lastClassifiedSignature = null;
let objectPresentInZone = false;
let resetStableTicks = 0;
let changeStableTicks = 0;
let lastClassificationAt = 0;

// ----- Start / stop camera -----
startCameraBtn.addEventListener('click', async () => {
  try {
    currentStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    cameraVideo.srcObject = currentStream;
    await applyMaxZoom(currentStream);
    baselineSignature = null;
    lastClassifiedSignature = null;
    objectPresentInZone = false;
    resetStableTicks = 0;
    changeStableTicks = 0;
    lastClassificationAt = 0;
    updateRoiOverlay();
    cameraStart.classList.add('hidden');
    cameraLive.classList.remove('hidden');
    resultSection.classList.remove('hidden');
    resultLoading.classList.add('hidden');
    resultContent.classList.add('hidden');
    paused = false;
    pauseResumeBtn.textContent = 'Pause';
    startAutoClassify();
  } catch (err) {
    alert('Camera access failed: ' + (err.message || 'Permission denied'));
  }
});

stopCameraBtn.addEventListener('click', () => {
  stopAutoClassify();
  stopCamera();
  cameraLive.classList.add('hidden');
  cameraStart.classList.remove('hidden');
  resultSection.classList.add('hidden');
  selectingBinZone = false;
  cameraRoi.classList.remove('selecting');
  baselineSignature = null;
  lastClassifiedSignature = null;
  objectPresentInZone = false;
  resetStableTicks = 0;
  changeStableTicks = 0;
  lastClassificationAt = 0;
  lockBinZoneBtn.textContent = 'Set Bin Zone';
  roiHint.textContent = 'Tap "Set Bin Zone", then tap the bin opening area once.';
});

function stopCamera() {
  if (currentStream) {
    currentStream.getTracks().forEach(t => t.stop());
    currentStream = null;
  }
  cameraVideo.srcObject = null;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function updateRoiOverlay() {
  const left = (roiCenterX - ROI_WIDTH_RATIO / 2) * 100;
  const top = (roiCenterY - ROI_HEIGHT_RATIO / 2) * 100;
  cameraRoi.style.left = `${left}%`;
  cameraRoi.style.top = `${top}%`;
  cameraRoi.style.width = `${ROI_WIDTH_RATIO * 100}%`;
  cameraRoi.style.height = `${ROI_HEIGHT_RATIO * 100}%`;
}

function buildFrameSignature(canvas) {
  const sampleCanvas = document.createElement('canvas');
  sampleCanvas.width = SIGNATURE_SIZE;
  sampleCanvas.height = SIGNATURE_SIZE;
  const sampleContext = sampleCanvas.getContext('2d', { willReadFrequently: true });
  sampleContext.drawImage(canvas, 0, 0, SIGNATURE_SIZE, SIGNATURE_SIZE);
  const imageData = sampleContext.getImageData(0, 0, SIGNATURE_SIZE, SIGNATURE_SIZE).data;
  const signature = new Uint8Array(SIGNATURE_SIZE * SIGNATURE_SIZE);

  for (let index = 0; index < signature.length; index += 1) {
    const offset = index * 4;
    signature[index] = Math.round((imageData[offset] + imageData[offset + 1] + imageData[offset + 2]) / 3);
  }

  return signature;
}

function getSignatureDiff(signatureA, signatureB) {
  if (!signatureA || !signatureB || signatureA.length !== signatureB.length) {
    return Number.POSITIVE_INFINITY;
  }

  let diffTotal = 0;
  for (let index = 0; index < signatureA.length; index += 1) {
    diffTotal += Math.abs(signatureA[index] - signatureB[index]);
  }

  return diffTotal / signatureA.length;
}

function shouldSendForClassification(signature) {
  if (!baselineSignature) {
    baselineSignature = signature;
    changeStableTicks = 0;
    return false;
  }

  const changeFromBaseline = getSignatureDiff(signature, baselineSignature);

  if (objectPresentInZone) {
    const changeFromLastClassified = getSignatureDiff(signature, lastClassifiedSignature);

    if (changeFromLastClassified >= OBJECT_SWAP_THRESHOLD) {
      const now = Date.now();
      if (now - lastClassificationAt >= MIN_CLASSIFY_GAP_MS) {
        lastClassificationAt = now;
        resetStableTicks = 0;
        return true;
      }
    }

    if (changeFromBaseline <= SCENE_RESET_THRESHOLD) {
      resetStableTicks += 1;
      if (resetStableTicks >= RESET_STABLE_TICKS_REQUIRED) {
        objectPresentInZone = false;
        resetStableTicks = 0;
        changeStableTicks = 0;
        baselineSignature = signature;
        lastClassifiedSignature = null;
        return 'reset';
      }
    } else {
      resetStableTicks = 0;
    }
    return false;
  }

  if (changeFromBaseline >= SCENE_CHANGE_THRESHOLD) {
    changeStableTicks += 1;
    if (changeStableTicks < CHANGE_TICKS_REQUIRED) {
      return false;
    }

    const now = Date.now();
    if (now - lastClassificationAt < MIN_CLASSIFY_GAP_MS) {
      return false;
    }
    objectPresentInZone = true;
    resetStableTicks = 0;
    changeStableTicks = 0;
    lastClassificationAt = now;
    return true;
  }

  changeStableTicks = 0;
  baselineSignature = signature;
  return false;
}

async function applyMaxZoom(stream) {
  const [track] = stream.getVideoTracks();
  if (!track || !track.getCapabilities || !track.applyConstraints) return;
  const caps = track.getCapabilities();
  if (typeof caps.zoom !== 'number') return;
  try {
    await track.applyConstraints({ advanced: [{ zoom: caps.zoom }] });
  } catch (err) {
    // Ignore on devices/browsers that do not allow runtime zoom changes.
  }
}

lockBinZoneBtn.addEventListener('click', () => {
  if (!currentStream) return;
  selectingBinZone = !selectingBinZone;
  if (selectingBinZone) {
    cameraRoi.classList.add('selecting');
    lockBinZoneBtn.textContent = 'Cancel Zone Select';
    roiHint.textContent = 'Tap once on the video where bins are located.';
  } else {
    cameraRoi.classList.remove('selecting');
    lockBinZoneBtn.textContent = 'Set Bin Zone';
    roiHint.textContent = 'Tap "Set Bin Zone", then tap the bin opening area once.';
  }
});

cameraVideo.addEventListener('click', (event) => {
  if (!selectingBinZone) return;
  const rect = cameraVideo.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;

  roiCenterX = clamp(x, ROI_WIDTH_RATIO / 2, 1 - ROI_WIDTH_RATIO / 2);
  roiCenterY = clamp(y, ROI_HEIGHT_RATIO / 2, 1 - ROI_HEIGHT_RATIO / 2);
  baselineSignature = null;
  lastClassifiedSignature = null;
  objectPresentInZone = false;
  resetStableTicks = 0;
  changeStableTicks = 0;
  lastClassificationAt = 0;
  updateRoiOverlay();

  selectingBinZone = false;
  cameraRoi.classList.remove('selecting');
  lockBinZoneBtn.textContent = 'Set Bin Zone';
  roiHint.textContent = 'Bin zone locked. Hold waste in that box only.';
});

function startAutoClassify() {
  stopAutoClassify();
  if (paused) return;
  // First classification after a short delay so video has a frame
  setTimeout(() => runClassify(), 800);
  autoClassifyTimer = setInterval(() => runClassify(), AUTO_CLASSIFY_INTERVAL_MS);
}

function stopAutoClassify() {
  if (autoClassifyTimer) {
    clearInterval(autoClassifyTimer);
    autoClassifyTimer = null;
  }
}

pauseResumeBtn.addEventListener('click', () => {
  paused = !paused;
  if (paused) {
    stopAutoClassify();
    pauseResumeBtn.textContent = 'Resume';
  } else {
    pauseResumeBtn.textContent = 'Pause';
    startAutoClassify();
  }
});

// Get current frame from live video as a File (for FormData)
function captureCurrentFrame() {
  if (!cameraVideo.videoWidth) return null;
  const canvas = document.createElement('canvas');
  const sourceWidth = cameraVideo.videoWidth;
  const sourceHeight = cameraVideo.videoHeight;
  canvas.width = sourceWidth;
  canvas.height = sourceHeight;
  canvas.getContext('2d').drawImage(
    cameraVideo,
    0,
    0,
    sourceWidth,
    sourceHeight,
    0,
    0,
    sourceWidth,
    sourceHeight,
  );
  const signature = buildFrameSignature(canvas);
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (!blob) { resolve(null); return; }
      resolve({
        file: new File([blob], 'frame.jpg', { type: 'image/jpeg' }),
        signature,
      });
    }, 'image/jpeg', 0.85);
  });
}

// ----- Auto-classify: send current frame to API -----
async function runClassify() {
  if (classifyInFlight || paused) return;
  const capturedFrame = await captureCurrentFrame();
  if (!capturedFrame) return;

  const classifyDecision = shouldSendForClassification(capturedFrame.signature);
  if (classifyDecision === 'reset') {
    clearResult();
    return;
  }
  if (!classifyDecision) return;

  const { file, signature } = capturedFrame;

  classifyInFlight = true;
  if (resultContent.classList.contains('hidden')) {
    resultLoading.classList.remove('hidden');
  }

  const form = new FormData();
  form.append('image', file);
  form.append('description', CLASSIFY_HINT);

  try {
    const res = await fetch(`${API_BASE}/classify`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || res.statusText);
    }
    lastResult = await res.json();
    // If model says nothing is present, clear and do not display
    if ((lastResult.category || '').toLowerCase() === 'none' ||
        (lastResult.item_name || '').toLowerCase() === 'nothing') {
      objectPresentInZone = false;
      lastClassifiedSignature = null;
      baselineSignature = capturedFrame ? capturedFrame.signature : null;
      clearResult();
    } else {
      lastClassifiedSignature = signature;
      showResult(lastResult);
      resultLoading.classList.add('hidden');
      resultContent.classList.remove('hidden');
    }
  } catch (e) {
    resultLoading.textContent = 'Error: ' + (e.message || 'Classification failed');
    resultLoading.classList.remove('hidden');
    resultContent.classList.add('hidden');
  } finally {
    classifyInFlight = false;
  }
}

function clearResult() {
  resultContent.classList.add('hidden');
  resultLoading.classList.add('hidden');
  binViz.querySelectorAll('.bin-compartment').forEach(el => {
    el.classList.remove('highlight-waste', 'highlight-recycling', 'highlight-compost', 'bin-open');
  });
  clarificationBox.classList.add('hidden');
  lastResult = null;
}

function playBinOpenAnimation() {
  binViz.querySelectorAll('.bin-compartment').forEach(el => el.classList.remove('bin-open'));
  requestAnimationFrame(() => {
    const open = binViz.querySelector('.bin-compartment.highlight-waste, .bin-compartment.highlight-recycling, .bin-compartment.highlight-compost');
    if (open) open.classList.add('bin-open');
  });
}

function showResult(r) {
  const cat = (r.category || '').toLowerCase();
  categoryPill.textContent = r.category || 'Unknown';
  categoryPill.className = 'category-pill ' + (cat === 'waste' ? 'waste' : cat === 'recycling' ? 'recycling' : 'compost');
  itemName.textContent = r.item_name || 'Item';
  confidenceText.textContent = 'Confidence: ' + Math.round((r.confidence || 0) * 100) + '%';
  reasoning.textContent = r.reasoning || '';
  tips.textContent = r.tips || '';

  binViz.querySelectorAll('.bin-compartment').forEach(el => {
    el.classList.remove('highlight-waste', 'highlight-recycling', 'highlight-compost');
    if (el.dataset.category === r.category) el.classList.add('highlight-' + cat);
  });
  playBinOpenAnimation();

  if (r.decision_mode === 'NEEDS_CLARIFICATION' && r.clarification_question && r.clarification_options?.length) {
    clarificationBox.classList.remove('hidden');
    clarificationQuestion.textContent = r.clarification_question;
    clarificationOptions.innerHTML = '';
    r.clarification_options.forEach(opt => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-secondary';
      b.textContent = opt;
      b.addEventListener('click', () => { clarificationBox.classList.add('hidden'); });
      clarificationOptions.appendChild(b);
    });
  } else {
    clarificationBox.classList.add('hidden');
  }

  feedbackCorrect.classList.add('hidden');
}

// ----- Feedback: show thank you, pause classify, then resume -----
function showThankYouAndResume(message) {
  feedbackBox.classList.add('hidden');
  thankYouMsg.textContent = message;
  thankYouMsg.classList.remove('hidden');
  paused = true;
  stopAutoClassify();
  setTimeout(() => {
    thankYouMsg.classList.add('hidden');
    thankYouMsg.textContent = '';
    feedbackBox.classList.remove('hidden');
    paused = false;
    startAutoClassify();
  }, THANK_YOU_DURATION_MS);
}

document.querySelector('.feedback-yes').addEventListener('click', async () => {
  await sendFeedback(lastResult?.category, true);
  showThankYouAndResume('Thank you!');
});

document.querySelector('.feedback-no').addEventListener('click', () => feedbackCorrect.classList.remove('hidden'));

document.querySelectorAll('.bin-option').forEach(btn => {
  btn.addEventListener('click', async () => {
    const cat = btn.dataset.category;
    await sendFeedback(cat, false);
    feedbackCorrect.classList.add('hidden');
    categoryPill.textContent = cat;
    categoryPill.className = 'category-pill ' + cat.toLowerCase();
    binViz.querySelectorAll('.bin-compartment').forEach(el => {
      el.classList.remove('highlight-waste', 'highlight-recycling', 'highlight-compost');
      if (el.dataset.category === cat) el.classList.add('highlight-' + cat.toLowerCase());
    });
    playBinOpenAnimation();
    showThankYouAndResume('Thank you for selecting the correct bin!');
  });
});

async function sendFeedback(finalCategory, wasCorrect) {
  if (!lastResult?.interaction_id) return;
  try {
    await fetch(`${API_BASE}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        interaction_id: lastResult.interaction_id,
        final_category: finalCategory,
        was_correct: wasCorrect,
      }),
    });
  } catch (e) {
    console.warn('Feedback failed', e);
  }
}

// ----- Stats -----
statsLink.addEventListener('click', (e) => {
  e.preventDefault();
  statsModal.classList.remove('hidden');
  loadStats();
});

closeStatsBtn.addEventListener('click', () => statsModal.classList.add('hidden'));
statsModal.addEventListener('click', (e) => { if (e.target === statsModal) statsModal.classList.add('hidden'); });

async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    const s = await res.json();
    statsBody.innerHTML = `
      <p><strong>Total items:</strong> ${s.total_items}</p>
      <p><strong>Overall accuracy:</strong> ${(s.accuracy_overall * 100).toFixed(0)}%</p>
      <p><strong>Items diverted from landfill:</strong> ${s.items_diverted_from_landfill}</p>
      <p><strong>Per category accuracy:</strong></p>
      <ul>${Object.entries(s.accuracy_per_category || {}).map(([k, v]) => `<li>${k}: ${(v * 100).toFixed(0)}%</li>`).join('')}</ul>
      ${(s.top_confusing_items?.length ? `<p><strong>Top confusing items:</strong></p><table><tr><th>Item</th><th>Correct rate</th></tr>${
        s.top_confusing_items.map(x => `<tr><td>${x.item}</td><td>${(x.correct_rate * 100).toFixed(0)}%</td></tr>`).join('')
      }</table>` : '')}
    `;
  } catch (e) {
    statsBody.innerHTML = '<p>Could not load stats.</p>';
  }
}
